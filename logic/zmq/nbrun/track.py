import json
import logging

import comm
from IPython.display import JSON
import IPython
from nbclient import NotebookClient

from traitlets import HasTraits, Unicode, default

from comm import create_comm, get_comm_manager
from comm.base_comm import BaseComm
from IPython.core.magic import line_magic, magics_class, Magics

# Tracks execution of a slow sub-notebook such as one waiting for real-time experiments to finish
# Progress is reported in two ways:
#  In cells of the sub-notebook after a %start <section> any variables starting with  <section>_
#  are "saved" on a %checkpoint. Ideally put %checkpoint in it's own cell. At this point all of the saved variables
#  are output as a JSON cell output.
#  Additionally, real-time progress notifications can be sent over a custom comm channel using IPython's messaging
#  system to allow any widgets in the parent notebook to display the current progress without delay
#  e.g. to actively show what the sub-notebook is doing and waiting on
#
# Start a tracker with Track.setup() to load IPython magics and start a comm channel
#
# On each instance a "comm_open" will be sent, causing the client end to invoke the handler method for opening a
# receiving handler. The client can keep these handlers separate or provide the same instance.

# Defines line magics:
# %start <section>
# %checkpoint
# %progress <msg>


class TimeoutException:
    def __init__(self, timeout):
        self.timeout = timeout

    def __repr__(self):
        return "Timed out after {}s".format(self.timeout)


# NbClient handles comm_open via handlers in comm_open_handlers so doesn't directly map to the standard
# CommManager used on the kernel end.

class NbClientCommManager:

    def __init__(self):
        self.channels = {}
        self.handlers = {}
        self.log = logging.getLogger('NbClientCommManager')

    class Handler:
        def __init__(self, target, handler):
            self.handler = handler
            self.log = logging.getLogger('NbClient.{}'.format(target))

        def handle_msg(self, msg: dict):
            try:
                data = msg['content']['data']
                self.log.debug("Handler received: {}".format(data))
                self.handler(data)
            except KeyError:
                self.log.debug("Handler received incomplete msg: {}".format(msg))

    def add_comm_open_handlers(self, nbc: NotebookClient):
        for target, handler in self.handlers.items():
            nbc.comm_open_handlers[target] = self.comm_open_handler

    def comm_open_handler(self, msg: dict):
        try:
            target_name = msg['content']['target_name']
            self.log.debug("Comm open {}".format(target_name))
            handler = self.handlers.get(target_name, None)
            if handler:
                self.log.debug("Found handler for channel {}, binding".format(target_name))
                return self.Handler(target_name, handler)
            else:
                return None
        except KeyError:
            return None


@magics_class
class Track(Magics):

    def __init__(self, ip: IPython):
        super(Track, self).__init__(ip)
        self.stage = None
        self._saved_state = {}
        self._status = {}
        self._summary = {}
        self.shell = ip
        self.log = logging.getLogger('track')
        self.comm_progress = comm.create_comm(target_name='progress')
        self.comm_status = comm.create_comm(target_name='status')
        self.comm_stop = comm.create_comm(target_name='stop_file')
        self.log.info("Started progress tracker")

    def send_progress_message(self, msg):
        self.log.debug("Sending progress msg: {} in stage {}".format(msg, self.stage))
        self.comm_progress.send({'message': msg, 'stage': self.stage})

    def send_progress(self, msg: dict):
        msg['stage'] = self.stage
        self.log.debug("Sending progress: {}".format(msg))
        self.comm_progress.send(msg)

    # tell the outer kernel where to put a stop file to cancel this kernel
    def send_stop_file(self, stop_file):
        self.log.debug("Sending stop_file: {}".format(stop_file))
        self.comm_stop.send(stop_file)

    def _encode_json(self, data, context=''):
        try:
            return json.dumps(data)
        except TypeError as e:
            self.log.warning("Failed to encode {} as json: {}".format(context, e.args))

    def send_status(self):
        status = self._encode_json(self._status, "<status for {}>".format(self.stage))
        summary = self._encode_json(self._summary, "<summary for {}>".format(self.stage))
        saved_state = self._encode_json(self._saved_state, "<saved_state for {}>".format(self.stage))
        self.comm_status.send({'status': status, 'summary': summary, 'saved_state': saved_state})

    # get variable value from this kernel context
    def _get(self, name, default_value=None):
        return self.shell.user_ns.get(name, default_value)

    # after every cell, peek into the variables and save state
    def _save(self):
        for k, v in self.shell.user_ns.items():
            if k.startswith(self.stage + '_'):
                self._saved_state[k] = v

        # transfer from <stage>_status to dict
        status_key = self._status_key()
        self._status[self.stage] = self._get(status_key, 'INCOMPLETE')

        # transfer from <stage>_summary to dict
        summary_key = self._summary_key()
        self._summary[self.stage] = self._get(summary_key, ' ')

    def _status_key(self):
        return '{}_status'.format(self.stage)

    def _summary_key(self):
        return '{}_summary'.format(self.stage)

    @classmethod
    def setup(cls):
        ip = IPython.get_ipython()
        mt = Track(ip)
        ip.events.register('post_run_cell', mt.post_run_cell)
        ip.register_magics(mt)
        return mt

    def post_run_cell(self, result):
        if self.stage is not None:
            self._save()
            self.send_status()

    @line_magic
    def start(self, stage):
        self.stage = stage
        self.shell.user_ns['track_stage'] = stage
        self._status[stage] = 'STARTED'
        self.send_status()
        self.send_progress_message("Starting stage <{}>".format(stage))

    @line_magic
    def status(self, status):
        if self.stage:
            self._status[self.stage] = status
            self.shell.user_ns[self._status_key()] = status
            self.send_status()

    @line_magic
    def summary(self, summary):
        if self.stage:
            self._summary[self.stage] = summary
            self.shell.user_ns[self._summary_key()] = summary
            self.send_status()

    @line_magic
    def progress(self, line):
        if not line.startswith("Waiting for "):
            # suppress the timer repeating lines
            print(line)
        self.send_progress_message(line)

    @line_magic
    def checkpoint(self, stage):
        if not stage:
            stage = self.stage

        self._save()
        self.status('DONE')
        self.send_progress_message("Done")

        checkpoint = JSON({'checkpoint': stage,
                           'saved_state': self._saved_state,
                           'status' : self._status,
                           'summary': self._summary},
                          expanded=False,
                          metadata={'type': 'checkpoint', 'root': 'checkpoint-{}'.format(self.stage)})
        return checkpoint

    def __del__(self):
        self.comm_progress.close()
        self.comm_stop.close()
        self.comm_status.close()


# Handler for the receiving end
# Traitlets let this be bound to a widget state

class TrackProgress(HasTraits):
    latest_message = Unicode()

    @default('latest_message')
    def _latest_message(self):
        return ''

    def __init__(self, **kwargs):
        super(TrackProgress, self).__init__(**kwargs)
        self.log = logging.getLogger('progress')

    def handle_msg(self, data: dict):
        message = data.get('message', '')
        stage = data.get('stage', '')
        self.latest_message = message



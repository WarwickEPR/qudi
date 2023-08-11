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
        self.current = None
        self.state = {}
        self.status = {}
        self.summary = {}
        self.shell = ip
        self.log = logging.getLogger('track')
        self.comm_progress = comm.create_comm(target_name='progress')
        self.comm_stop = comm.create_comm(target_name='stop_file')
        self.log.info("Started progress tracker")

    def send_progress_message(self, msg):
        self.log.debug("Sending progress msg: {} in stage {}".format(msg, self.current))
        self.comm_progress.send({'message': msg, 'stage': self.current})

    def send_progress(self, msg: dict):
        msg['stage'] = self.current
        self.log.debug("Sending progress: {}".format(msg))
        self.comm_progress.send(msg)

    def send_stop_file(self, stop_file):
        self.log.debug("Sending stop_file: {}".format(stop_file))
        self.comm_stop.send(stop_file)

    def _get(self, name, default_value=None):
        return self.shell.user_ns.get(name, default_value)

    def _save(self):
        for k, v in self.shell.user_ns.items():
            if k.startswith(self.current + '_'):
                self.state[k] = v
        status_key = self._status_key()
        self.status[status_key] = self._get(status_key, 'INCOMPLETE')
        summary_key = self._summary_key()
        self.summary[summary_key] = self._get(summary_key, ' ')

    def _status_key(self):
        return '{}_status'.format(self.current)

    def _summary_key(self):
        return '{}_status'.format(self.current)

    @classmethod
    def setup(cls):
        ip = IPython.get_ipython()
        mt = Track(ip)
        ip.events.register('post_run_cell', mt.post_run_cell)
        ip.register_magics(mt)
        return mt

    def post_run_cell(self, result):
        if self.current is not None:
            self._save()

    @line_magic
    def start(self, line):
        self.current = line
        self.shell.user_ns['track_current'] = line
        self.send_progress_message("Starting stage <{}>".format(line))

    @line_magic
    def status(self, line):
        if self.current:
            self.shell.user_ns[self._status_key()] = line

    @line_magic
    def summary(self, line):
        if self.current:
            self.shell.user_ns[self._summary_key()] = line

    @line_magic
    def checkpoint(self, line):
        if line:
            checkpoint = line
        else:
            checkpoint = self.current
        return JSON({'checkpoint': checkpoint,
                     'state': self.state,
                     'status': self.status,
                     'summary': self.summary},
                    expanded=False,
                    metadata={'type': 'checkpoint', 'root': 'checkpoint-{}'.format(self.current)})

    @line_magic
    def progress(self, line):
        self.send_progress_message(line)

    def __del__(self):
        self.comm_progress.close()
        self.comm_stop.close()


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



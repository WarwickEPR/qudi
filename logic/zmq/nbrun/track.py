import asyncio
import logging
import time

from nbclient import NotebookClient
from nbclient.exceptions import CellExecutionError
import nbformat
from ipywidgets import GridspecLayout, Button, Layout, Label
from IPython.display import JSON
import IPython
import json
from .. data.timestamp import get_timestamp
from traitlets import HasTraits, Unicode, default

from IPython.core.magic import line_magic, magics_class, Magics
from ipykernel.comm import Comm

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

        self.comm = Comm(target_name='progress', data="Started progress tracker")
        self.log.info("Started progress tracker")

    def send_status(self, msg):
        self.log.debug(msg)
        self.comm.send(msg)

    def _get(self, name, default_value=None):
        return self.shell.user_ns.get(name, default_value)

    def _save(self):
        for k, v in self.shell.user_ns.items():
            if k.startswith(self.current + '_'):
                self.state[k] = v
        status_key = '{}_status'.format(self.current)
        summary_key = '{}_summary'.format(self.current)
        self.status[status_key] = self._get(status_key, 'INCOMPLETE')
        self.summary[summary_key] = self._get(summary_key, ' ')

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
        self.comm.send(line)

    def __del__(self):
        self.comm.close()


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

    def handle_msg(self, msg):
        data = msg['content']['data']
        self.latest_message = data
        self.log.debug(data)

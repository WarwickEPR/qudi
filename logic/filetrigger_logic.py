"""
This module watches files to communicate with an external process
such as scripted triggering of Andor Solis measurements. Once the
external task signals completion, refocus and retrigger the external task.
Optionally, script an action before and after the external task
e.g. to flip a mirror

Qudi is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Qudi is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Qudi. If not, see <http://www.gnu.org/licenses/>.

Copyright (c) the Qudi Developers. See the COPYRIGHT.txt file at the
top-level directory of this distribution and at <https://github.com/Ulm-IQO/qudi/>
"""

from collections import OrderedDict
from logic.generic_logic import GenericLogic
from core.module import Connector
from core.configoption import ConfigOption
from qtpy import QtCore
import os.path
import datetime


class FileTriggerLogic(GenericLogic):
    """
    A logic module for integration with external processes via files
    """
    _modclass = 'filetriggerlogic'
    _modtype = 'logic'

    _start_file = ConfigOption('start_file', missing='error')
    _done_file = ConfigOption('done_file', missing='error')
    _flip_mirror = ConfigOption('flip_mirror', missing='info')
    task_done = QtCore.Signal()
    optimiserlogic = Connector(interface='OptimizerLogic')
    poilogic = Connector(interface='PoiManagerLogic')

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)
        self._running = False
        self._start_file = None
        self._done_file = None
        self._timer = None
        self._label = ''

    def on_activate(self):
        """ Connect and configure the access to the FPGA.
        """
        self._timer = QtCore.QTimer()
        self._timer.timeout.connect(self._poll_done_file)
        self.task_done.connect(self._after_task, QtCore.Qt.QueuedConnection)
        # Connect callback for a finished refocus
        self.optimiserlogic().sigRefocusFinished.connect(
            self._optimiser_done, QtCore.Qt.QueuedConnection)

    @staticmethod
    def flip_mirror(self):
        # for now, assume nicard is loaded
        # this could be handled by the external control box
        nicard.digital_channel_switch('/Dev1/port0/line8', mode=False)
        nicard.digital_channel_switch('/Dev1/port0/line8', mode=True)
        nicard.digital_channel_switch('/Dev1/port0/line8', mode=False)

    def _poll_done_file(self):
        if os.path.exists(self._done_file):
            self.task_done.emit()

    def _after_task(self):
        # called after "done" file appears

        # stop polling
        self.timer.stop()

        # clean up done file
        os.remove(self._done_file)

        # flip mirror back to photon counters
        if self._flip_mirror:
            self.flip_mirror()

        # trigger optimiser
        self.optimiserlogic().optimise_poi_position()

        # when optimiser finishes, consider another run
        # idle until then

    def start_task(self):
        self._running = True
        self._run_task()

    def _generate_run_name(self):
        return '_'.join([self._label, self.poilogic.active_poi(), datetime.datetime.now().strftime("%Y%m%d-%H%M%S")])

    def _run_task(self):
        run_name = self._generate_run_name()

        # flip mirror to Andor
        if self._flip_mirror:
            self.flip_mirror()

        # start external process by creating "start" file then poll every 5s for "done"
        with open(self._start_file, 'w') as f:
            f.write(run_name)
            f.close()

        self.timer.start(5000)

        # wait for done condition to fire and run _after_task

    def _optimiser_done(self):
        # triggered when optimiser completes
        if self._running:
            self._run_task()

    def setup_task(self, label):
        self._running = False
        self._label = label

    def stop_task(self):
        self._task_running = False

    def on_deactivate(self):
        """ Reverse steps of activation

        @return int: error code (0:OK, -1:error)
        """
        self.task_done.disconnect(self._after_task)
        self.timer.disconnect(self._poll_done_file)
        self.optimiserlogic.sigRefocusFinished.disconnect(self._optimiser_done)
        return 0

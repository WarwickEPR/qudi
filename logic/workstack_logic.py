# -*- coding: utf-8 -*-
"""
Provides support with running long sequences of operations by waiting for signals
to sequence them correctly without freezing the main thread e.g. a series of
images or performing several actions at a list of POI

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

from core.module import Connector
from core.util.mutex import Mutex
from logic.generic_logic import GenericLogic

from qtpy import QtCore

class WorkstackLogic(GenericLogic):

    """
    This module provides support with running sequences of actions
    """
    _modclass = 'workstacklogic'
    _modtype = 'logic'

    # declare connectors
    optimizer1 = Connector(interface='OptimizerLogic')
    scannerlogic = Connector(interface='ConfocalLogic')
    savelogic = Connector(interface='SaveLogic')

    signal_timer_updated = QtCore.Signal()
    signal_work_started = QtCore.Signal()
    signal_work_stopped = QtCore.Signal()

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)
        super().__init__(config=config, **kwargs)

        # timer and its handling for the periodic refocus
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.timer_fired)

        self.targets = []
        self.actions = []

        # not actually a stack but a running order of actions
        # which can change during execution. The next action to
        # run is indexed by sp
        self.stack = []
        self.sp = 0
        self.running = False
        self.target_index = 0
        self.multipleTargets = False
        self.ctx = dict()

        # locking for thread safety
        self.threadlock = Mutex()

    def on_activate(self):
        """ Initialisation performed during activation of the module.
        """

        self._optimizer_logic = self.get_connector('optimizer1')
        self._confocal_logic = self.get_connector('scannerlogic')
        self._save_logic = self.get_connector('savelogic')

        # listen for the refocus to finish
        self._optimizer_logic.sigRefocusFinished.connect(self.refocused)
        self._confocal_logic.signal_stop_scanning.connect(self.finished_image)
        self._confocal_logic.signal_xy_data_saved.connect(self.finished_saving)

    def on_deactivate(self):
        # connections should ideally disconnect
        self._optimizer_logic.sigRefocusFinished.disconnect(self.refocused)
        self._confocal_logic.signal_stop_scanning.disconnect(self.finished_image)
        self._confocal_logic.signal_xy_data_saved.disconnect(self.finished_saving)
        return

    def timer_fired(self):
        self.run_next_action()

    def refocused(self):
        self.log.info("Finished refocusing")
        self.run_next_action()

    def finished_saving(self):
        self.log.info("Finished saving")

        self.run_next_action()

    def finished_image(self):
        self.log.info("Finished image")
        self.run_next_action()

    def start_work(self):
        if self.multipleTargets:
            if len(self.targets) > 0:
                self.target_index = 0
            else:
                self.log.warn('Workstack - nothing to do')

        self.stack = list(self.actions)
        self.sp = 0
        self.running = True
        self.do_action()            

    def current_target(self):
        self.targets[self.target_index]

    def stop_work(self):
        self.running = False

    def reset_stack(self):
        self.sp = 0
        self.stack = list(self.actions)

    @staticmethod
    def _run(action, args):
        if isinstance(action, str):
            return exec(action)
        else:
            return action(*args)

    def do_action(self):
        if self.running:
            action = self.stack[self.sp]
            if action == 'wait':
                pass   # wait until a signal moves things on
            elif action == 'start again':
                self.reset_stack()
            elif action == 'skip':
                self.log.info("Skipping to next")
                self.run_on_next_target()
            elif isinstance(action, tuple):
                (desc, action, args) = self.stack[self.sp]
                self.log.info("Doing: {}".format(desc))
                self._run(action, args)
                self.run_next_action()
            else:
                self._run(action, ())
                self.run_next_action()

    def advance_sp(self):
        if self.sp >= len(self.stack):
            if self.multipleTargets:
                if self.target_id >= len(self.targets):
                    # done!]
                    self.log.info("Finished")
                    self.stop_work()
                else:
                    self.target_id += 1
                    self.log.info("Moving on to {}".format(self.current_target()))
                    self.reset_stack()
            else:
                self.log.info("Finished")
                self.stop_work()
        else:
            self.sp += 1

    def run_next_action(self):
        if self.running:
            self.advance_sp()
            self.do_action()

    #####################
    # actions
    #####################

    def start_timer(self, duration=60, repeat=False):
        """ Starts a timer.

        @param float duration: (optional) the time until expires
        @param float update: (optional) the time between update signals
        @param bool repeat: (optional) whether to repeat

        @return int: error code (0:OK)
        """

        self.log.info('WorkStack timer started {}s'.format(duration))
        self.timer.setSingleShot(not repeat)
        self.timer.start(int(duration*1000))
        return 0

    # insert an action at the current sp (i.e. that'll happen next
    def insert_action(self, action):
        self.stack.insert(self.sp, action)

    def insert_wait(self):
        self.stack.insert('wait')

    def goto_poi(self):
        poi = self.current_target()
        self._optimizer_logic.optimise_poi(poi)
        self.insert_wait()

    def say_hello(self):
        self.log.info("Hello world!")

    def load_just_focus(self):
        self.actions = [self.goto_poi, self.run_on_next]

    def load_focus_psat(self):
        self.actions = [self.goto_poi, self.psat_save_set, self.run_on_next]

    def load_demo_loop(self):
        self.actions = [('Log message', self.log.info, ["Wait for it..."]),
                        ('Start timer', self.start_timer, (10,)),
                        'wait',
                        self.say_hello,
                        'start again']

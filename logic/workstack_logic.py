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
import sys
from logic.generic_logic import GenericLogic
from collections import OrderedDict
import numpy as np
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
    sequencegeneratorlogic = Connector(interface='GenericLogic')
    savelogic = Connector(interface='SaveLogic')

    signal_timer_updated = QtCore.Signal()
    signal_start_timer = QtCore.Signal()
    signal_work_started = QtCore.Signal()
    signal_work_stopped = QtCore.Signal()

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)
        super().__init__(config=config, **kwargs)

        self.targets = []
        self.actions = []

        # not actually a stack but a running order of actions
        # which can change during execution. The next action to
        # run is indexed by sp
        self.stack = []
        self._store = dict()
        self.save_values = []
        self.sp = 0
        self.running = False
        self.target_index = 0
        self.timer_duration = 60
        self.multipleTargets = False
        self.ctx = dict()
        self.waiting_on = ''

        # locking for thread safety
        self.threadlock = Mutex()

    def on_activate(self):
        """ Initialisation performed during activation of the module.
        """

        self._optimizer_logic = self.get_connector('optimizer1')
        self._confocal_logic = self.get_connector('scannerlogic')
        self._sequence_logic = self.get_connector('sequencegeneratorlogic')
        self._save_logic = self.get_connector('savelogic')

        # timer and its handling for the periodic refocus
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.timer_fired)

        # listen for the refocus to finish
        self._optimizer_logic.sigRefocusFinished.connect(self.refocused, QtCore.Qt.QueuedConnection)
        self._confocal_logic.signal_stop_scanning.connect(self.finished_image, QtCore.Qt.QueuedConnection)
        self._confocal_logic.signal_xy_data_saved.connect(self.finished_saving, QtCore.Qt.QueuedConnection)
        self._sequence_logic.sigSampleEnsembleComplete.connect(self.pulse_sequence_built, QtCore.Qt.QueuedConnection)
        self.signal_start_timer.connect(self._start_timer, QtCore.Qt.QueuedConnection)  # so this thread can handle

    def on_deactivate(self):
        # connections should ideally disconnect
        self._optimizer_logic.sigRefocusFinished.disconnect(self.refocused)
        self._confocal_logic.signal_stop_scanning.disconnect(self.finished_image)
        self._confocal_logic.signal_xy_data_saved.disconnect(self.finished_saving)
        self.timer.timeout.disconnect()
        return

    def timer_fired(self):
        if self.waiting_on == '' or self.waiting_on == 'timer':
            self.waiting_on = ''
            self.run_next_action()

    def refocused(self, caller, p):
        self.log.info("Finished refocusing")
        self._confocal_logic.set_position('workstack', *p)
        if self.waiting_on == '' or self.waiting_on == 'refocus':
            self.waiting_on = ''
            self.run_next_action()

    def pulse_sequence_built(self, asset):
        self.log.info("Pulse sequence uploaded: {}".format(asset))
        if self.waiting_on == '' or self.waiting_on == 'pulse upload':
            self.waiting_on = ''
            self.run_next_action()

    def finished_saving(self):
        self.log.info("Finished saving")
        self.run_next_action()

    def finished_image(self):
        self.log.info("Finished image")
        self.run_next_action()

    def start_work(self):
        if len(self.targets) > 0:
            self.multipleTargets = True
            self.target_index = 0
            t = self.current_target()
            if t not in self._store.keys():
                self._store[t] = dict()
        self.stack = list(self.actions)
        self.sp = 0
        # self._store = dict()
        self.running = True
        self.do_action()            

    def current_target(self):
        if self.multipleTargets:
            return self.targets[self.target_index]
        else:
            return '_'

    def do_next_target(self):
        if self.multipleTargets and self.target_index < (len(self.targets)-1):
            self.target_index += 1
            t = self.current_target()
            if t not in self._store.keys():
                self._store[t] = dict()
            self.reset_stack()
            self.log.info("Skipping to next: {}".format(self.current_target()))
            self.do_action()
        else:
            self.log.info("Skipping to next, but finished")
            self.stop_work()

    def stop_work(self):
        self.running = False

    def reset_stack(self):
        self.sp = 0
        self.stack = list(self.actions)

    def _run(self, desc, action, args):
        try:
            if isinstance(action, str):
                return exec(action)
            else:
                return action(*args)
        except:
            self.log.error("Running {} failed! {}".format(desc, sys.exc_info()[0]))
            self.do_next_target()

    def do_action(self):
        if self.running:
            action = self.stack[self.sp]
            if action == 'wait':
                self.waiting_on = '' # wait until any signal moves things on
            elif action == 'wait timer':
                self.waiting_on = 'timer'
            elif action == 'wait pulse upload':
                self.waiting_on = 'pulse upload'
            elif action == 'wait refocus':
                self.waiting_on = 'refocus'
            elif action == 'start again':
                self.reset_stack()
                self.run_next_action()
            elif action == 'next target':
                self.log.info("Moving to next target")
                self.do_next_target()
            elif isinstance(action, tuple):
                (desc, action, args) = self.stack[self.sp]
                args = [x if x != '_X_' else self.current_target() for x in args]
                d = desc.format(*args)
                if action == 'log':
                    self.log.info(desc.format(*args))
                elif action == 'timer':
                    secs, = args
                    self.log.info("Waiting for {} s for {}".format(secs, desc))
                    self.start_timer(secs)
                else:
                    self.log.info("Doing: " + d)
                    self._run(d, action, args)
                self.run_next_action()
            else:
                self._run(action, action, ())
                self.run_next_action()

    def load_store_from_file(self, path):
        with open(path, 'r') as f:
            for l in f.readlines():
                if l.startswith('#'):
                    continue
                data = l.split()
                name = data[0]
                values = [float(x) for x in data[1:]]
                self._store[name] = dict()
                i = 0
                for k in self.save_values:
                    self._store[name][k] = values[i]
                    i += 1

    def advance_sp(self):
        if self.sp >= len(self.stack)-1:
            self.log.debug("Reached end of stack")
            if self.multipleTargets:
                if self.target_index >= len(self.targets)-1:
                    # done!]
                    self.log.info("Finished")
                    self.stop_work()
                else:
                    self.target_index += 1
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

    def store(self, name, value):
        k = self.current_target()
        if k not in self._store.keys():
            self._store[k] = dict()
        self._store[k][name] = value

    def fetch(self, name):
        t = self.current_target()
        if t not in self._store.keys():
            self.log.warn("Missing key! {}".format(t))
            self.do_next_target()
        elif name not in self._store[t].keys():
            self.log.warn("Missing key! {}  {}".format(t, name))
            return 0.0
        return self._store[self.current_target()][name]

    def save(self):
        # File path and name
        filepath = self._save_logic.get_path_for_module(module_name='Workstack')

        # We will fill the data OrderedDict to send to savelogic
        data = OrderedDict()
        targets = sorted(x[0] for x in self._store.items())
        data['Target'] = np.array(targets)
        for k in self.save_values:
            data[k] = np.array([self._store[t][k] if k in self._store[t].keys() else 0.0 for t in targets])

        self._save_logic.save_data(data, filepath=filepath, filelabel='workstack', fmt=['%s'] + ['%.6e'] * len(self.save_values))
        self.log.debug('Workstack data saved to:\n{0}'.format(filepath))

        return 0

    #####################
    # actions
    #####################

    def start_timer(self, duration=60):
        self.timer_duration = duration
        self.signal_start_timer.emit()

    def _start_timer(self):
        """ Starts a timer.

        @param float duration: (optional) the time until expires
        @param float update: (optional) the time between update signals
        @param bool repeat: (optional) whether to repeat

        @return int: error code (0:OK)
        """

        self.log.info('WorkStack timer started {}s'.format(self.timer_duration))
        self.timer.setSingleShot(True)
        self.timer.start(int(self.timer_duration*1000))
        return 0

    # insert an action at the current sp (i.e. that'll happen next)
    def insert_action(self, action):
        self.stack.insert(self.sp, action)

    def insert_actions(self, actions):
        modified_stack = self.stack[0:self.sp+1] + actions + self.stack[self.sp+1:]
        self.stack = modified_stack

    def insert_wait(self):
        self.stack.insert('wait')

    def goto_poi(self):
        poi = self.current_target()
        self._optimizer_logic.optimise_poi(poi)
        self.insert_wait()

    def info(self, msg):
        self.log.info(msg)

    def say_hello(self):
        self.log.info("Hello world!")

    def load_just_focus(self):
        self.actions = [self.goto_poi, self.run_on_next]

    def load_focus_psat(self):
        self.actions = [self.goto_poi, self.psat_save_set, self.run_on_next]

    def load_demo_loop(self):
        self.save_values = ['a', 'world']
        self.actions = [('Log message', self.log.info, ["Wait for it..."]),
                        ('Start timer', self.start_timer, (5,)),
                        (lambda: self.store('a', 2)),
                        (lambda: self.store('world', 3)),
                        'wait',
                        self.say_hello,
                        (lambda: self.log.info(self.fetch('a'))),
                        (lambda: self.log.info(self.fetch('a'))),
                        self.save,
                        'start again']


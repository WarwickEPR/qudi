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

import logging

from collections import OrderedDict
from core.module import Connector
from core.util.mutex import Mutex
from logic.generic_logic import GenericLogic

class WorkStackLogic(GenericLogic):

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
        self._save_logic.sig

    def on_deactivate(self):
        return

    def timer_fired(self):
        self.run_next_action()

    def refocused(self):
        self.run_next_action()

    def finished_saving(self):
        self.run_next_action()

    def finished_image(self):
        self.run_next_action()

    def start_work(self):
        if multipleTargets:
            if length(targets) > 0:
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

    def _run(action):
        if type(action) == str:
            return exec(action)
        else:
            return action()

    def do_action(self):
        if self.running:
          action = self.stack[sp]
          if action == 'wait':
            pass   # wait until a signal moves things on
          elif type(action) == type([]):
            action = action[0]
            args = action[1:]
            if action == 'if':
                if length(args != 3):
                   self.log.error('Bad "if" condition, expected ["if",cond,[alist],[blist]]')
                   self.stop_work()
                else:
                   [cond,a,b] = args
                   if self._run(cond):
                       self.stack.insert(sp,a)
                   else:
                       self.stack.insert(sp,b)
                       self.next_action() 
          else:
            self._run(self.stack[self.sp])
            self.next_action()

    def next_action(self):
        if self.sp >= length(self.stack):
            if multipleTargets:
                if target_id >= length(self.targets):
                    # done!
                    self.stop_work()
                else:
                    target_id += 1
                    self.stack = list(self.actions)
            else:
                self.stack = list(self.actions)
        else:
            self.sp += 1

    def run_next_action(self):
        self.next_action()
        self.do_action()

    def start_timer(self, duration=60, update=10, repeat=False):
        """ Starts a timer.

        @param float duration: (optional) the time until expires
        @param float update: (optional) the time between update signals
        @param bool repeat: (optional) whether to repeat

        @return int: error code (0:OK)
        """

        self.log.info('WorkStack timer started {}s'.format(during))
        self.timer.setSingleShot(not repeat)
        self.timer.start(duration)
        return 0

    def run_on_next(self):
        if self.multipleTargets and self.target_index <= length(self.targets):
            self.target_index += 1
        else:
            self.log.info("Finished workstack")
            self.stop_work()
    
    def insert_action(self,action):
        self.stack.insert(self.sp,action)

    def insert_wait(self):
        self.stack.insert('wait')

    def goto_poi(self):
        poi = self.current_target()
        self._optimizer_logic.optimise_poi(poi)
        self.insert_wait()

    # TODO: Don't update the sample position
    # if the site isn't "bright" after focusing, move on
    def goto_poi_if_bright(self):
        poi = self.current_target()
        self._optimizer_logic.move_to_poi(poi)
        self.insert_wait()
        # insert another action to check countrate
        countrate = 0

    def psat_save_set(self):
        nicard.set_up_scanner_clock()
        nicard.set_up_scanner()
        o = nicard.scan_voltage(v)
        nicard.close_scanner()
        nicard.close_scanner_clock()
        d = np.append(o, [])

        powers = power_est(v)
        fit = fit_psat_aom(v-3,d)
        vsat = fit.best_values['P_sat'] + 3.0
        summary = "# Isat {} counts at\n# {} V\n# {} mW\n# fit {}\n\n".format(fit.best_values['I_sat'],vsat,power_est(vsat),fit.best_values)
        print('fitted Isat {} at {}V {}mW'.format(fit.best_values['I_sat'],vsat,power_est(vsat)))

        with open(r"C:\Users\Confocal\Desktop\psat-{}.csv".format(p), 'w', newline='') as csvfile:
            csvfile.write(summary)
            pwriter = csv.writer(csvfile)
            pwriter.writerows([v, powers, d, fit.best_fit])

            print('Done Psat {}'.format(p))

            if vsat > 7.0:
                V = 7.0
            else:
                V = vsat
            nicard.set_voltage(V)


        return d

    def power_est(v):
        return (0.0166 * v - 0.0522) * 40



    def load_just_focus(self):
        self.actions = [ self.goto_poi, self.run_on_next ]

    def load_focus_psat(self):
        self.actions = [ self.goto_poi, self.psat_save_set, self.run_on_next ]

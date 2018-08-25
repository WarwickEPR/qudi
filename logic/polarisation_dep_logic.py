# -*- coding: utf-8 -*-
"""
This file contains the Qudi logic class for performing polarisation dependence measurements.

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
from logic.generic_logic import GenericLogic
from qtpy import QtCore


class PolarisationDepLogic(GenericLogic):
    """This logic module rotates polarisation and records signal as a function of angle.

    """

    _modclass = 'polarisationdeplogic'
    _modtype = 'logic'

    ## declare connectors
    counterlogic = Connector(interface='CounterLogic')
    savelogic = Connector(interface='SaveLogic')
    motor = Connector(interface='MotorInterface')

    # signal for the homing of the motor
    signal_homing_started = QtCore.Signal()
    signal_homing_finished = QtCore.Signal()

    # signal for the rotation during measurement
    signal_rotation_started = QtCore.Signal()
    signal_rotation_finished = QtCore.Signal()

    def on_activate(self):
        """ Initialisation performed during activation of the module.
        """

        self._counter_logic = self.counterlogic()
#        print("Counting device is", self._counting_device)

        self._save_logic = self.savelogic()

        self._hwpmotor = self.motor()

        # Initialise measurement parameters
        self.scan_length = 360
        self.scan_speed = 10 #not yet used

        # Connect signals
        self.signal_homing_started.connect(self._start_homing_timer)
        self.signal_homing_finished.connect(self.rotate_polarisation, QtCore.Qt.QueuedConnection)

        self.signal_rotation_started.connect(self._start_movement_timer)
        self.signal_rotation_finished.connect(self.finish_scan, QtCore.Qt.QueuedConnection)

        # -------------------
        # Setup Timers
        # -------------------
        self.timer_value = 300

        self.homing_timer = QtCore.QTimer()
        self.homing_timer.timeout.connect(self.check_home)

        self.movement_timer = QtCore.QTimer()
        self.movement_timer.timeout.connect(self.check_motor_stopped)


        # Start off by knowing we're not moving, obviously
        self.was_moving = False

    def on_deactivate(self):
        """ Deinitialisation performed during deactivation of the module.
        """

        # -------------------
        # Disconnect the signals
        # -------------------
        self.signal_homing_started.disconnect()
        self.signal_homing_finished.disconnect()
        self.signal_rotation_started.disconnect()
        self.signal_rotation_finished.disconnect()

        # -------------------
        # Stop timers
        # -------------------
        self.homing_timer.stop()
        self.movement_timer.stop()

        return 0

    def _start_homing_timer(self):
        self.homing_timer.start(self.timer_value)

    def _stop_homing_timer(self):
        self.homing_timer.stop()

    def _start_movement_timer(self):
        self.movement_timer.start(self.timer_value)

    def _stop_movement_timer(self):
        self.movement_timer.stop()


    def run_polarisation(self):
        """Do a simple pol dep measurement.
        """
        # Set up measurement
        self._hwpmotor.move_abs({'waveplate':0})

        # Set moving to true
        self.was_moving = True

        # check that motor is at zero
        self.signal_homing_started.emit()

    def check_home(self):
        """ Check that the HWP is at zero before starting the measurement """
        get_pos = self._hwpmotor.get_pos({'waveplate'})
        current_pos = round(get_pos['waveplate'])

        if (current_pos == 0) or (current_pos == 360):
            # Honey, we're home; do what's next
            self._stop_homing_timer()
            self.signal_homing_finished.emit()

            # and once at home, we're not moving
            self.was_moving = False
        else:
            # still moving to home
            self.was_moving = True
            self.signal_homing_started.emit()

    def rotate_polarisation(self):
        # Start saving here
        self._counter_logic.start_saving()

        # Tell HWP to move by the scan length
        self._hwpmotor.move_rel({'waveplate': int(self.scan_length)})

        # Set off with moving is true again
        self.was_moving = True

        # know when to stop
        self.signal_rotation_started.emit()

    def check_motor_stopped(self):
        motor_status = self._hwpmotor.get_status({'waveplate'})
        self.log.debug(motor_status['waveplate'][0])

        if motor_status['waveplate'][0] != 0:
            self.was_moving = True

        elif self.was_moving:
            self.log.info('Motor finished moving')
            self.was_moving = False

            # stop the timer
            self.movement_timer.stop()

            # move to the next item
            self.signal_rotation_finished.emit()
        else:
            pass

    def finish_scan(self):
        self.log.info('rotation finished, saving data')
        self._counter_logic.save_data()
#        self._counter_logic.stopCount()
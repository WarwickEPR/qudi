# -*- coding: utf-8 -*-
"""
This file contains the Qudi stepper interface logic class.

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

from qtpy import QtCore
from collections import OrderedDict
import numpy as np
import time

from core.connector import Connector
from logic.generic_logic import GenericLogic
from core.util.mutex import Mutex


class StepperLogic(GenericLogic):
    """ This logic module allows simple UI control of hardware steppers (tailored for low temp attocube stages)

    """
    sigMoveNumberOfSteps = QtCore.Signal(str, int)
    sigStop = QtCore.Signal()

    # declare connectors
    stepper1 = Connector(interface='MotorInterface')

    def __init__(self, config, **kwargs):
        """ Create StepperLogic object with connectors.

        @param dict config: module configuration
        @param dict kwargs: optional parameters
        """
        super().__init__(config=config, **kwargs)

        #locking for thread safety
        self.threadlock = Mutex()

        # self.log.debug('The following configuration was found.')
        #
        # # checking for the right configuration
        # for key in config.keys():
        #     self.log.debug('{0}: {1}'.format(key, config[key]))

        # # in bins
        # self._count_length = 300
        # self._smooth_window_length = 10
        # self._counting_samples = 1      # oversampling
        # # in hertz
        # self._count_frequency = 50
        return

    def on_activate(self):
        """ Initialisation performed during activation of the module.
        """
        # Connect to hardware and save logic
        self._stepping_device = self.stepper1()
        self.axes = self._stepping_device.axis()
        #TODO might want to get the constraints to allow the UI to place limits
        return

    def on_deactivate(self):
        """ Deinitialisation performed during deactivation of the module.
        """
         # self.sigCountDataNext.disconnect()
        return

    def get_constraints(self):
        """ Returns the frequency and voltage limits for the connected axes """
        constraints = self._stepping_device.get_constraints()
        axes = self.axes
        relevant_constraints = {}
        for ax in axes:
            relevant_constraints[ax] = {}
            relevant_constraints[ax]['frequency'] = (constraints[ax]['vel_min'], constraints[ax]['vel_max'])
            relevant_constraints[ax]['voltage'] = (constraints[ax]['acc_min'], constraints[ax]['acc_max'])

        return relevant_constraints

    def move_number_of_steps(self, axis, steps):
        """ Move the specified number of steps in the specified axis ('x', 'y', or 'z')

        @return the new current position for the specified axis"""
        self._stepping_device.move_rel({axis: steps})
        return self._stepping_device.get_pos()[axis]

    def get_current_location(self):
        """ Return the current position for all axes in steps """
        return self._stepping_device.get_pos()

    def get_frequency(self, axis):
        """ Get the frequency for the specified axis

        @return the actual values set in hardware """
        return self._stepping_device.frequency(axis)

    def get_voltage(self, axis):
        """ Get the voltage for the specified axis

        @return the actual values set in hardware """
        return self._stepping_device.voltage(axis)

    def set_frequency(self, axis, frequency):
        """ Set the frequency for the given axis

        @return the actual values set in hardware """
        self._stepping_device.frequency(axis, value=frequency)
        time.sleep(0.1)
        return self.get_frequency(axis)

    def set_voltage(self, axis, voltage):
        """ Set the voltage for the given axis

        @return the actual values set in hardware """
        self._stepping_device.voltage(axis, value=voltage)
        time.sleep(0.1)
        return self.get_voltage(axis)

    def get_dci_status(self):
        """ Get the DC Input status for all axes """
        return self._stepping_device.get_DC_input_status(self.axes)

    def enable_DC_input(self, axis):
        """ Enable DC inputs for the specified axes. Note that these are automatically
        disabled once you step the axis"""
        self._stepping_device.enable_DC_input(axis)

    def disable_DC_input(self, axis):
        """ Disable DC inputs for the specified axes. Note that these are automatically
        disabled once you step the axis"""
        self._stepping_device.disable_DC_input(axis)

    def ground(self, axis):
        """ Ground the specified axes """
        self._stepping_device.ground(axis)

    def unground(self, axis):
        """ Unground the specified axes """
        self._stepping_device.unground(axis)

    def get_grounding_status(self):
        """ Get the grounding status for all axes """
        return self._stepping_device.get_grounding_status(self.axes)

    def measure_capacitance(self):
        """ Measure the capacitance for all connected axes

        @return capacitance in F """
        return self._stepping_device.capacitance(self.axes)

    def refresh_hardware_status(self):
        """ Update hardware configuration values for all axes - doesn't include measuring capacitance """
        freq = self.get_frequency(self.axes)
        voltage = self.get_voltage(self.axes)
        dci = self.get_dci_status()
        grounded = self.get_grounding_status()

        hardware_values = {}
        for idx, ax in enumerate(self.axes):
            hardware_values[ax] = {}
            hardware_values[ax]['frequency'] = freq[idx]
            hardware_values[ax]['voltage'] = voltage[idx]
            hardware_values[ax]['dci'] = dci[idx]
            hardware_values[ax]['grounded'] = grounded[idx]

        return hardware_values

    def set_origin(self):
        """ Set the origin of the stage system """
        self._stepping_device.calibrate()

    def stop(self):
        """ Stop all movement """
        self._stepping_device.abort()

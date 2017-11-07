# -*- coding: utf-8 -*-

"""
This module contains the Qudi interface file for piezo stepper.

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

from logic.generic_logic import GenericLogic
from core.module import Connector


class StepperLogic(GenericLogic):

    """ This is the logic module to control simple piezo stepper hardware.
    """

    _modtype = 'StepperLogic'
    _modclass = 'logic'

    stepper = Connector(interface='PiezoStepperInterface')
    _hw = None

    def on_activate(self):
        """ Initialisation performed during activation of the module.
        """

        # Connectors
        self._hw = self.get_connector('stepper')

    def reset_hardware(self):
        """ Resets the hardware, so the connection is lost and other programs
            can access it.

        @return int: error code (0:OK, -1:error)
        """
        pass

    def get_step_voltage(self, axis):
        """ Gets the voltage of the steps.

        @param axis: string specifying axis
        @return float: voltage
        """
        return self._hw.get_step_voltage(axis)

    def set_step_voltage(self, axis, voltage=None):
        """ Sets the voltage of the steps.

        @param axis: string specifying axis
        @param float voltage: float specifying the voltage used per step

        @return int: error code (0:OK, -1:error)
        """
        return self._hw.set_step_voltage(axis, voltage)

    def get_step_frequency(self, axis):
        """ Gets the frequency of the steps.

        @param axis: string specifying axis
        @return int: frequency
        """
        return self._hw.get_step_frequency(axis)

    def set_step_frequency(self, axis, frequency=None):
        """ Sets the frequency of the steps.

        @param axis: string specifying axis
        @param float frequency: int specifying the frequency of steps

        @return int: error code (0:OK, -1:error)
        """
        return self._hw.set_step_frequency(axis, frequency)

    def get_axis_mode(self, axis):
        """ Gets the mode of the axis

        @param axis: string specifying axis
        @return string: mode of axis
        """
        return self._hw.get_axis_mode(axis)

    def set_axis_mode(self, axis, mode):
        """ Sets the mode of the axis

        @param axis: string specifying axis
        @param mode: string specifying the mode

        @return int: error code (0:OK, -1:error)
        """
        return self._hw.set_axis_mode(axis, mode)

    def get_voltage_range(self, axis):
        """ Get the range of allowed voltage

        @param axis: string specifying axis

        @return [float,float] of low, high voltage limits"""
        return self._hw.get_voltage_range(axis)

    def get_frequency_range(self, axis):
        """ Get the range of allowed frequencies

        @param axis: string specifying axis

        @return [int,int] of low, high frequency limits"""
        return self._hw.get_frequency_range(axis)

    def step_up(self, axis=None, steps=1):
        """ Steps the positioner up a given number of steps

        @param axis: string selecting axis
        @param steps: Number of steps, None equals one

        @return: error code (0:OK, -1:error)
        """
        return self._hw.step_up(axis, steps)

    def step_down(self, axis=None, steps=1):
        """ Steps the positioner down a given number of steps

        @param axis: string selecting axis
        @param steps: Number of steps, None equals one

        @return: error code (0:OK, -1:error)
        """
        return self._hw.step_down(axis, steps)

    def step_up_continuously(self, axis=None):
        """ Steps the positioner up until stopped

        @param axis: string selecting axis
        @param steps: Number of steps, None equals one

        @return: error code (0:OK, -1:error)
        """
        return self._hw.step_up_continuously(axis)

    def step_down_continuously(self, axis=None):
        """ Steps the positioner down until stopped

        @param axis: string selecting axis
        @param steps: Number of steps, None equals one

        @return: error code (0:OK, -1:error)
        """
        return self._hw.step_down_continuously(axis)

    def stop_axis(self, axis=None):
        """ Stops the axis

        @param axis: string selecting axis

        @return: error code (0:OK, -1:error)
        """
        return self._hw.stop_axis(axis)

    def stop_all_axes(self):
        """ Stops all axes

        @return: error code (0:OK, -1:error)
        """
        return self._hw.stop_all_axes()

    def get_offset(self, axis):
        """ Gets the offset voltage for an axis

        @param axis: string selecting axis

        @return: float voltage
        """
        return self._hw.get_offset(self, axis)

    def set_offset(self, axis, voltage):
        """ Sets the offset voltage for an axis

        @param axis: string selecting axis
        @param offset: voltage

        @return: error code (0:OK, -1:error)
        """
        return self._hw.set_offset(self, axis, voltage)

    def scan_offset(self, axis, offset_list, dwell):
        """ Sets off a scan of a predefined list of voltages

        @param axis: string selecting axis
        @param offset_list: string selecting offset list from configuration
        @param dwell: approximate number of ms to dwell at each point

        @return: error code (0:OK, -1:error)"""
        return self._hw.scan_offset(self, axis, offset_list, dwell)
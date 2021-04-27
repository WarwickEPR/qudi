# -*- coding: utf-8 -*-

"""
This module contains the Qudi Hardware module attocube ANC350, via the PyANC350 module.

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

import PyANC350.PyANC350v4
import time

from core.module import Base
from core.configoption import ConfigOption
from interface.confocal_stepper_interface import ConfocalStepperInterface
import numpy as np


class AttoCubeStepper(Base, ConfocalStepperInterface):
    """ 
    """

    _modtype = 'AttoCubeStepper'
    _modclass = 'hardware'

    _voltage_range_stepper = ConfigOption('voltage_range_stepper', [0, 60], missing='warn')
    axis = ConfigOption('axis', {}, missing='error')
    _step_range = ConfigOption('step_range', {}, missing='error')
    _feedback = ConfigOption('position_feedback', {}, missing='error')

    attocube_axis_num = {'x': 1, 'y': 2, 'z': 3} # Converts _attocube_axis keys to numbers for pyANC350
    
    # instantiates the Positioner class in PyANC350v4
    pyanc = Positioner()
    
    def on_activate(self):
        """ Initialisation performed during activation of the module.

        """
        config = self.getConfiguration()
        # some default values for the hardware:
        # Todo: This needs to be calculated by a more complicated formula depnding on the measured capacitance.
        # Todo: voltage range should be defined for each axis, the same for frequency
        self._voltage_range_stepper_default = [0, 60]
        self._frequency_range_default = [0, 10000]

        # Todo this needs to be update with checking every time it is started.

        # Todo get rid of all fine/coarse definition stuff, only step voltage will remain

        self._attocube_modes = {"stepping": "stp", "ground": "gnd", "Input": "inp", "off": "off", "offsetstepping": "stp+", "offset": "off"}
        # Todo finish attocube modes with sensible names
        # mode_list = ["gnd", "inp", "stp", "off", "stp+", "stp-"]

        # handle all the parameters given by the config
        self._attocube_axis = {}  # dictionary contains the axes and the specific controller
        self._attocube_axis_range = {}  # dictionary contains the axes stepping range
        self._position_feedback = {}
        default_range = [0, 3]
        
        for i in self.axis:
            for j in dict(i).items():
                self._attocube_axis[j[0]] = j[1]
                self.log.info(self._attocube_axis) #Just to check what is in _attocube_axis, remove after noting
        axis_list = []
        feedback_list = []
        for i in self._step_range.keys():
            if i not in self._attocube_axis.keys():
                self.log.error("%s is not a possible axis.\n Therefore it is not possible to define "
                               "the attocube step range for it. This range will be omitted", i)
                continue
            step_min, step_max = float(self._step_range[i][0]), float(self._step_range[i][1])
            if step_min < step_max:
                self._attocube_axis_range[i] = [step_min, step_max]
            else:
                self.log.warn('Configuration %s  of attocube step range for %s incorrect, taking [0 , '
                              '5.] (mm) instead.', self._step_range[i], i)
                self._attocube_axis_range[i] = [0, 5.]
            axis_list.append(i)

        for i in self._feedback:
            for j in dict(i).items():
                if j[0] not in self._attocube_axis.keys():
                    self.log.error("%s is not a possible axis.\n Therefore it is not possible to define "
                                   "a feedback status for it. This feedback option will be omitted", i)
                    continue
                if isinstance(j[1], bool):
                    self._position_feedback[j[0]] = j[1]
                else:
                    self.log.warn(
                        'Configuration type %s  of feedback status for %s incorrect, taking default (False) instead',
                        type(j[1]), j[0])
                    self._position_feedback[j[0]] = False
                feedback_list.append(j[0])

        # check if all axis have a step range defined:
        for i in self._attocube_axis.keys():
            if i not in axis_list:
                self.log.error("%s channel has no attocube step range defined. Taking default [0,5.] (mm) instead.")
                self._attocube_axis_range[i] = [0, 5.]
        # check if all axis have a feedback status defined:
        for i in self._attocube_axis.keys():
            if i not in feedback_list:
                self.log.error(
                    "%s channel has no feedback status defined. Taking default (False) instead.")
                self._position_feedback[i] = False

        # clean up variables
        del self._feedback
        del self.axis

        # Todo: this needs to be read from a specifically still to be made text file depending on
        #  the capacitance
        self._frequency_range = dict()
        if 'frequency_range' in config.keys():
            if int(config['frequency_range'][0]) < int(config['frequency_range'][1]):
                for axis in self._attocube_axis.keys():
                    self._frequency_range[axis] = [int(config['frequency_range'][0]),
                                                   int(config['frequency_range'][1])]
            else:
                for axis in self._attocube_axis.keys():
                    self._frequency_range[axis] = [int(config['frequency_range'][0]),
                                                   int(config['frequency_range'][1])]
                self.log.warning(
                    'Configuration ({}) of frequency_range incorrect, taking [0,60] instead.'
                    ''.format(config['frequency_range']))
        else:
            self.log.warning('No frequency_range configured taking [0,60] instead.')
            for axis in self._attocube_axis.keys():
                self._frequency_range[axis] = [int(config['frequency_range'][0]),
                                               int(config['frequency_range'][1])]

        self._initalize_axis()
        # This reads all the values from the hardware and checks if values ly inside defined boundaries
        self._get_all_hardwaresettings()

    def on_deactivate(self):
        """ Deinitialisation performed during deactivation of the module.

        @param object e: Event class object from Fysom. A more detailed
                         explanation can be found in method activation.
        """

        pyanc.disconnect()
        self.connected = False

    # =================== Attocube Communication ========================
    # Attocube communication is handled by the pyANC350 module and corresponding .dll files


    # =================== General Methods ==========================================

# TODO: add some tests that the attocubes can carry out to measure the step size.
# For now, leave this as a pass
    def change_step_size(self, axis, step_size, temp):
        """Changes the step size of the attocubes according to a list give in the config file
        @param str  axis: axis  for which steps size is to be changed
        @param float step_size: The wanted step size in nm
        @param float temp: The estimated temperature of the attocubes

        @return: float, float : Actual step size and used temperature"""

        """
        voltage = step_size
        # Todo here needs to be a conversion done
        self.set_step_amplitude(axis, voltage)
        """
        pass

    def set_step_amplitude(self, axis, voltage=None):
        """Sets the step voltage/amplitude for axis for the ANC350 via pyANC350

        @param str axis: key of the dictionary self._attocube_axis for the axis to be changed
        @param float voltage: the stepping amplitude/voltage the axis should be set to
        @return int: error code (0:OK, -1:error)
        """

        # Todo: probably is would be more clever to if voltage is none before testing it against the range
        if voltage < self._voltage_range_stepper[0] or voltage > self._voltage_range_stepper[1]:
            self.log.error(
                'Voltages {0} exceed the limit, the positions have to '
                'be adjusted to stay in the given range.'.format(voltage))
            return -1

        if voltage is not None:
            if axis in self._attocube_axis.keys():
                # Should _axis_amplitude be defined at top of file?
                self._axis_amplitude[axis] = voltage
                # Note: axis is a string, so must convert to integer for pyANC350
                return pyanc.setAmplitude(self.attocube_axis_num[axis],voltage)
            self.log.error("axis {} not in list of possible axes".format(self._attocube_axis))
            return -1

    def get_step_amplitude(self, axis):
        """ Checks the amplitude of a step for a specific axis

        @param str axis: the axis for which the step amplitude is to be checked
        @return float: the step amplitude of the axis
        """
        if axis in self._attocube_axis.keys():
            self._axis_amplitude[axis] = pyanc.getAmplitude(self.attocube_axis_num[axis])
            if (self._voltage_range_stepper[0] > self._axis_amplitude[axis] or
                    self._axis_amplitude[axis] >
                    self._voltage_range_stepper[1]):
                self.log.error(
                    "The voltage of {} V of axis {} in the ANC350 lies outside the defined range{},{]".format(
                        self._axis_amplitde[axis], axis, self._voltage_range_stepper[0],
                        self._voltage_range_stepper[1]))
            return self._axis_amplitude[axis]
        self.log.error("axis {} not in list of possible axes".format(self._attocube_axis))
        return -1

    def set_step_freq(self, axis, freq=None):
        """Sets the step frequency for axis for the ANC350 via pyANC350

        @param str axis: key of the dictionary self._attocube_axis for the axis to be changed
        @param float freq: the stepping frequency the axis should be set to
        @return int: error code (0:OK, -1:error)
        """
        # Todo this need to have a check added if freq is inside freq range
        # Todo I need to add decide how to save the freq for the three axis and if decided update the current freq

        if freq is not None:
            if axis in self._attocube_axis.keys():
                self._axis_frequency[axis] = freq
                return pyanc.setFrequency(self.attocube_axis_num[axis],freq)
            self.log.error("axis {} not in list of possible axes".format(self._attocube_axis))
            return -1
        self.log.info("No frequency was given so the step frequency was not changed.")
        return 0

    def get_step_freq(self, axis):
        """ Checks the step frequency for a specific axis

        @param str axis: the axis for which the frequency is to be checked
        @return float: the step amplitude of the axis
        """
        if axis in self._attocube_axis.keys():
            self._axis_frequency[axis] = pyanc.getFrequency(self.attocube_axis_num[axis])
            if (self._frequency_range[axis][0] > self._axis_frequency[axis] or self._axis_frequency[axis] >
                    self._frequency_range[axis][1]):
                self.log.error(
                    "The value of {} V of axis {} in the ANC350 lies outside the defined range{},{]".format(
                        self._axis_frequency[axis], axis, self._frequency_range[axis][0],
                        self._frequency_range[axis][1]))
            return self._axis_frequency[axis]
        self.log.error("axis {} not in list of possible axes {}".format(axis, self._attocube_axis))
        return -1

# Switches between: stepping, ground, input, off, offsetstepping, offset
# Not really sure how to interpret this, leave as pass for now.
    def set_axis_mode(self, axis, mode):
        """Changes Attocube axis mode

        @param str axis: axis to be changed, can only be part of dictionary axes
        @param str mode: mode to be set
        @return int: error code (0: OK, -1:error)
        """
        """
        if mode in self._attocube_modes.keys():
            if axis in self._attocube_axis.keys():
                command = "setm {} {}".format(self._attocube_axis[axis],
                                              self._attocube_modes[mode])
                result = self._send_cmd(command)
                if result == 0:
                    self._axis_mode[axis] = mode
                    return 0
                else:
                    self.log.error(
                        "Setting axis {} to mode {} failed".format(self._attocube_axis[axis],
                                                                   mode))
            else:
                self.log.error(
                    "axis {} not in list of possible axes {}".format(axis, self._attocube_axis))
                return -1
        else:
            self.log.error("mode {} not in list of possible modes".format(mode))
            return -1
        """
        pass

# See set_axis_mode. Leave as pass for now.
    def get_axis_mode(self, axis):
        """ Checks the mode for a specific axis

        @param str axis: the axis for which the frequency is to be checked
        @return float: the mode of the axis, -1 for error
        """
        """
        if axis in self._attocube_axis.keys():
            command = "getm {}".format(self._attocube_axis[axis])
            result = self._send_cmd(command, read=True)
            if result[0] == -1:
                return -1
            mode_line = result[1][-3].split()
            for mode in self._attocube_modes:
                if self._attocube_modes[mode] == mode_line[-1]:
                    self._axis_mode[axis] = mode
                    return self._axis_mode[axis]
            else:
                self.log.error(
                    "Current mode of controller %s  for axis %s not in list of modes %s ",
                        mode_line[-1], axis, self._attocube_modes)
                return -1
        self.log.error("axis {} not in list of possible axes".format(self._attocube_axis))
        return -1
        """
        pass

# Leave as pass for now
# TODO: Confirm that this relates to fine control system
    def set_DC_in(self, axis, on):
        """Changes Attocube axis DC input status

        @param str axis: axis to be changed, can only be part of dictionary axes
        @param bool on: if True is turned on, False is turned off
        @return int: error code (0: OK, -1:error)
        """
        """
        if axis in self._attocube_axis.keys():
            if on:
                dci = "on"
            else:
                dci = "off"
            command = "setdci {} ".format(self._attocube_axis[axis]) + dci
            result = self._send_cmd(command)
            if result == 0:
                self._axis_dci[axis] = dci
                return 0
            else:
                return -1
        self.log.error("axis {} not in list of possible axes".format(self._attocube_axis))
        return -1
        """
        pass

# TODO: Confirm that this relates to fine control system
    def get_DC_in(self, axis):
        """ Checks the status of the DC input for a specific axis

        @param str axis: the axis for which the input is to be checked
        @return bool: True for on, False for off or error
        """
        """
        if axis in self._attocube_axis.keys():
            command = "getdci {}".format(self._attocube_axis[axis])
            result = self._send_cmd(command, read=True)
            if result[0] == -1:
                return False
            dci_result = result[1][-3].split()
            self._axis_dci[axis] = dci_result[-1]
            if dci_result[-1] == "off":
                return False
            return True
        self.log.error("axis {} not in list of possible axes".format(self._attocube_axis))
        return False
        """
        pass

"""
It is not clear why these functions exist. They are not present in Cofocal stepper or piezo stepper interfaces.
Their definitions do not make sense. Possibly related to AC voltage amplitude?

    def set_AC_in(self, axis, on):
        Changes the status of the AC input for a specific axis

        @param str axis: axis to be changed, can only be part of dictionary axes
        @param bool on: if True is turned on, False is turned off
        @return int: error code (0: OK, -1:error)
        
        if axis in self._attocube_axis.keys():
            if on:
                aci = "on"
            else:
                aci = "off"
            command = "setdci {} ".format(self._attocube_axis[axis]) + aci
            result = self._send_cmd(command)
            if result == 0:
                self._axis_aci[axis] = aci
                return 0
            else:
                return -1
        self.log.error("axis {} not in list of possible axes".format(self._attocube_axis))
        return -1

    def get_AC_in(self, axis):
         Checks the status of the AC input for a specific axis

        @param str axis: the axis for which the input is to be checked
        @return bool: True for on, False for off, -1 for error
        
        if axis in self._attocube_axis.keys():
            command = "getaci {}".format(self._attocube_axis[axis])
            result = self._send_cmd(command, read=True)
            if result[0] == -1:
                return -1
            aci_result = result[1][-3].split()
            self._axis_aci[axis] = aci_result[-1]
            if aci_result[-1] == "off":
                return False
            return True
        self.log.error("axis {} not in list of possible axes".format(self._attocube_axis))
        return -1
"""

# For now leave this as a pass, but if cryostat can be integrated, setting this up could be handy
    def _temperature_change(self, new_temp):
        """
        Changes parameters in attocubes to keep requirements like step size and scan speed
        constant for different temperatures
        @param float new_temp: the new temperature of the setup
        @return int: error code (0: OK, -1:error)
        """
        """
        # if a temperature change happened the capacitance of the attocubes changed and need to be
        # remeasured
        axis = self.get_stepper_axes()
        for i in self._attocube_axis.keys():  # get all axis names
            if axis[self._attocube_axis[i]]:  # check it the axis actually exists
                self._measure_capacitance(i)
        self.update_freq_range()
        pass
        # Todo: This needs to make a certain kind of change, as this then depends on
        # temperature. also maybe method name is not appropriate
        """
        pass

    def _measure_capacitance(self, axis):
        """ Measures the attocube capacitance for a given axis

        @param str axis: the axis for which the frequency is to be checked
        @return float: the capacitance of the axis in F, -1 for error
        """
        if axis in self._attocube_axis.keys():
            Cap = pyanc.measureCapacitance(self.attocube_axis_num[axis])
            if Cap == 0:
                self.log.error("Something is wrong with measuring capacitance of the attocubes.")
                return -1
            else:
                return Cap
        self.log.error("axis {} not in list of possible axes".format(self._attocube_axis))
        return -1

# Calls _measure_capacitance(), can't get capacitance without measuring it.
    def _get_capacitance(self, axis):
        """ Reads the  saved attocube capacitance for a given axis from the hardware

        @param str axis: the axis for which the frequency is to be checked
        @return float: the capacitance of the axis in F, -1 for error
        """
        return self._measure_capacitance(axis)

# This could be left as is.
    def _get_all_hardwaresettings(self):
        axis = self.get_stepper_axes()
        for i in self._attocube_axis.keys():  # get all axis names
            if axis[self._attocube_axis[i] - 1]:  # check it the axis actually exists
                self.get_step_amplitude(i)
                self.get_step_freq(i)
                self.get_axis_mode(i)
                self.get_DC_in(i)
                self.get_AC_in(i)
                self._get_capacitance(i)

            else:
                self.log.error("axis {} was specified as number {} on ANC350\n  but this axis "
                               "doesn't exist in the ANC350".format(i, self._attocube_axis[i]))
                return -1
        else:
            return 0

# This can be left as is.
    def _initalize_axis(self):
        """ Initialises all axes values, setting them to 0.
        This should only be called when making a new instance.
        """
        axis = self.get_stepper_axes()
        self._axis_amplitude = {}
        self._axis_frequency = {}
        self._axis_mode = {}
        self._axis_dci = {}
        self._axis_aci = {}
        self._axis_capacitance = {}

        for i in self._attocube_axis.keys():  # get all axis names
            if axis[self._attocube_axis[i] - 1]:  # check it the axis actually exists
                self._axis_amplitude[i] = 0
                self._axis_frequency[i] = 0
                self._axis_mode[i] = ""
                self._axis_dci[i] = ""
                self._axis_aci[i] = ""
                self._axis_capacitance[i] = 0
            else:
                self.log.error("axis {} was specified as number {} on ANC300\n  but this axis "
                               "doesn't exist in the ANC300".format(i, self._attocube_axis[i]))

    # =================== ConfocalStepperInterface Commands ========================
# This can be left as is.
    def reset_hardware(self):
        """ Resets the hardware, so the connection is lost and other programs
            can access it.

        @return int: error code (0:OK, -1:error)
        """
        self.log.warning('Attocube Device does not need to be reset.')
        pass

    def get_position_feedback(self, axis_name):
        """Checks if the hardware is a closed loop hardware with position feedback
        return bool: if True the hardware has a position feedback"""
        # For the ANC350, feedback is always possible
        return True

# Stepper range should be defined in config file.
    def get_position_range_stepper(self, axis):
        """ Returns the physical range of the stepper.

        @param str axis_name: the axis for which the range is to be checked

        @return dict: key: axis name as sting (e.g. "x"), value the stepper range in mm
        """
        if axis not in self._attocube_axis.keys():
            self.log.error("axis {} not in list of possible axes".format(self._attocube_axis))
            return -1
        return self._attocube_axis_range[axis]

    def set_position_range_stepper(self, axis, my_range=None):
        """ Sets the physical range of the stepper.

        @param str axis: the axis for which the range is to be changed
        @param float [2] my_range: 2 value float array containing the new lower and upper limit

        @return int: error code (0:OK, -1:error)
        """
        if axis not in self._attocube_axis.keys():
            self.log.error("axis {} not in list of possible axes".format(self._attocube_axis))
            return -1
        if my_range is None:
            my_range = [0, 5]

        if not isinstance(my_range, (frozenset, list, set, tuple, np.ndarray,)):
            self.log.error('Given range is no array type.')
            return -1

        if len(my_range) != 2:
            self.log.error(
                'Given range should have dimension 2, but has {0:d} instead.'
                ''.format(len(my_range)))
            return -1

        if my_range[0] > my_range[1]:
            self.log.error(
                'Given range limit {0:d} has the wrong order.'.format(my_range))
            return -1

        self._attocube_axis_range[axis] = my_range
        return 0

# Can be left as is, should be defined in config file.
    def set_amplitude_range_stepper(self, my_range=None):
        """ Sets the voltage range of the attocubes.

        @param float [2] my_range: array containing lower and upper limit

        @return int: error code (0:OK, -1:error)
        """
        if my_range is None:
            my_range = [0, 60.]

        if not isinstance(my_range, (frozenset, list, set, tuple, np.ndarray,)):
            self.log.error('Given range is no array type.')
            return -1

        if len(my_range) != 2:
            self.log.error(
                'Given range should have dimension 2, but has {0:d} instead.'
                ''.format(len(my_range)))
            return -1

        if my_range[0] > my_range[1]:
            self.log.error('Given range limit {} has the wrong order.'.format(my_range))
            return -1

        self._voltage_range_stepper = my_range
        self._update_freq_range()
        return 0

    def get_amplitude_range_stepper(self):
        """Returns the current possible stepping voltage range of the stepping device for all axes

        @return list: voltage range of stepper
        """
        return self._voltage_range_stepper

# Not present in Confocal interface file.
    def update_freq_range(self):
        """"Updates the constraints on the frequency range

        @return int: error code (0:OK, -1:error)
        """
        # Todo:Write after text file was written
        pass

    def get_freq_range_stepper(self):
        """Returns the current possible stepping voltage range of the stepping device for all axes
        @return list: voltage range of scanner
        """
        return self._frequency_range

# TODO: Work out what this method actually does. Possibly related to Positioner.discover()
    # Todo: It might make sense to return a libary of axis ("x", "y", "z" etc. against booleans) check.
    def get_stepper_axes(self):
        """"
        Checks which axes of the hardware have a reaction by the hardware

         @return list: list of booleans for each possible axis, if true axis exists

         On error, return empty list
        """
        """
        # TOdo: Check if I did the same split list problem more then once
        axis = []
        for i in range(5):
            command = "getm {}".format(i + 1)
            result = self._send_cmd(command, read=True)
            if result[0] == -1:
                res = result[1]
                if result[1][1] == "Wrong axis type":
                    axis.append(False)
                else:
                    self.log.error('The command {} did the expected axis response, '
                                   'but{}'.format(command, result[1][1].split()[-3]))
            else:

                axis.append(True)
        return axis
        """
        pass

    def get_stepper_axes_use(self):
        """ Find out how the axes of the stepping device are used for confocal and their names.

        @return list(str): list of axis dictionary

        Example:
          For 3D confocal microscopy in Cartesian coordinates, ['x':1, 'y':2, 'z':3] is a sensible 
          value.
          If you only care about the number of axes and not the assignment and names 
          use get_stepper_axes
        """
        return self._attocube_axis

# This is the tricky one. Needs to have access to all three types of motion.
# Currently has access to single step and continuous mode
# TODO: must add autoMove function too, but will likely require a change to the logic module
# NOTE: autoMove uses units m, but Qudi uses units mm
# TODO: add a way for Qudi to check that attocube has moved
    def move_attocube(self, axis, mode=True, direction=True, steps=1):
        """Moves attocubes either continuously or by a number of steps
        in the up or down direction.

        @param str axis: axis to be moved, can only be part of dictionary axes
        @param bool mode: Set if attocubes steps an amount of steps (True) or moves continuously until stopped (False)
        @param bool direction: True for up or out, False for down or "in" movement direction
        @param int steps: number of steps to be moved, ignore for continuous mode
        @return int:  error code (0: OK, -1:error)
        """

        if axis in self._attocube_axis.keys():
            i = 0
            if mode and direction:
                while i < steps:
                    pyanc.startSingleStep(self.attocube_axis_num[axis], 0)
                    i += 1
            elif mode and not direction:
                while i < steps:
                    pyanc.startSingleStep(self.attocube_axis_num[axis], 1)
                    i += 1
            elif not mode and direction:
                pyanc.startContinuousMove(self.attocube_axis_num[axis], 1, 0)
            elif not mode and not direction:
                pyanc.startContinuousMove(self.attocube_axis_num[axis], 1, 1)
            else:
                self.log.error(
                    'You tried to move an attocube, but somehow didnt assign mode or direction a boolean value in move_attocube()')
        else:
            self.log.error("axis {} not in list of possible axes".format(self._attocube_axis))
            return -1

    def stop_attocube_movement(self, axis):
        """Stops attocube motion on specified axis,
        only necessary if attocubes are stepping in continuous mode

        @param str axis: axis to be moved, can only be part of dictionary axes
        @return int: error code (0: OK, -1:error)
        """
        if axis in self._attocube_axis.keys():
            return pyanc.startContinuousMove(self.attocube_axis_num[axis], 0, 0)
        else:
            self.log.error("axis {} not in list of possible axes".format(self._attocube_axis))
            return -1

# Will definitely stop all continuous motion. Not sure about single step while loops above.
# TODO: Add stop commands for all types of motion
    def stop_all_attocube_motion(self):
        """Stops any attocube motion

        @return 0
        """
        for axis in self._attocube_axis.keys():
            pyanc.startContinuousMove(self.attocube_axis_num[axis], 0, 0)

        self.log.info("any attocube stepper motion has been stopped")
        return 0

# =================== Piezo Stepper Interface ========================

    def get_position_range(self):
        return self.get_amplitude_range_stepper()

# TODO: Cant use get_position_range_stepper as it returns a dict, so need to create method that returns 3x2 array
    def set_position_range(self, myrange=None):
        pass

    def set_amplitude(self, amp=None):
        for axis in self._attocube_axis.keys():
            self.set_step_amplitude(self.attocube_axis_num[axis], amp)
        return 0

    def set_temperature(self):
        pass

# This is a single step function, should call the move_attocube method
    def step(self):
        pass

# This should call Positioner.disconnect or smth
    def close_stepper(self):
        pass

# =================== Confocal Scanner Interface (?) ========================

# From confocal_scanner_interface
# Unclear how important this method is
    def get_scanner_position(self):
        """ Get the current position of the scanner hardware.

        @return tuple(float): current position as a tuple. Ex : (x, y, z, a).
        """
        pos = (pyanc.getPosition(1), pyanc.getPosition(2), pyanc.getPosition(3))
        return pos

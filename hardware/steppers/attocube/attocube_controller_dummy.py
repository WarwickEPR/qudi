# -*- coding: utf-8 -*-

"""
This module contains the dummy Qudi Hardware module attocube ANC300 .

---

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

import time
import random

from core.module import Base
from core.configoption import ConfigOption
from interface.motor_interface import MotorInterface


class AttocubeControllerDummy(Base, MotorInterface):
    """ Module to interface the attocube ANC300 hardware, that controls steppers used to position samples or
    devices.

    Example config :
    attocubedummy:
        module.Class: 'steppers.attocube.attocube_controller_dummy.AttocubeControllerDummy'
        axis:
            x:
                id: 1
                position_range: [-2.5e-3, 2.5e-3]
                voltage_range: [0,70]
                frequency_range: [0,300]
                feedback: False
                'frequency': 100
                'voltage': 50
            y:
                id: 2
                position_range: [-2.5e-3, 2.5e-3]
                voltage_range: [0,70]
                frequency_range: [0,300]
                feedback: False
                'frequency': 100
                'voltage': 50
            z:
                id: 3
                position_range: [-2.5e-3, 2.5e-3]
                voltage_range: [0,50]
                frequency_range: [0,200]
                feedback: False
                'frequency': 100
                'voltage': 30
    """

    _default_axis = {
        'voltage_range': [0, 60],
        'frequency_range': [0, 10000],
        'position_range': [0, 5],
        'feedback': False,
        'frequency': 20,
        'voltage': 30,
        'capacitance': None,
        'busy': False,
        'dci' : False
    }
    _connected = False

    _axis_config = ConfigOption('axis', {}, missing='error')
    _current_position = None

    def on_activate(self):
        """ Initialisation performed during activation of the module """
        self._check_axis()

        self._initialize_axis()
        self.calibrate()

    def _check_axis(self):
        """ Check that the axis in the config file are ok and complete missing values with default """
        for name in self._axis_config:
            if 'id' not in self._axis_config[name]:
                self.log.error('id of axis {} is not defined in config file.'.format(name))
            # check _axis_config and set default value if not defined
            for key in self._default_axis:
                if key not in self._axis_config[name]:
                    self._axis_config[name][key] = self._default_axis[key]

    def _initialize_axis(self):
        """ Initialize axis with the values from the config """
        for name in self._axis_config:
            self.capacitance(name)  # capacitance leaves axis in step mode
            self.frequency(name, self._axis_config[name]['frequency'])
            self.voltage(name, self._axis_config[name]['voltage'])

    def on_deactivate(self):
        """ Deinitialisation performed during deactivation of the module. """
        pass

    def _parse_axis(self, axis):
        """ Take a valid axis or list/tuple of axis and return a list with valid axis name.

        @param axis: a valid axis or list/tuple of axis

        @return: a list with valid axis name

        By doing this we have the same universal axis input for all module functions

        For example :
        'x' -> ['x']
        1 -> ['x']
        ['x', 2] -> ['x', 'y']
        """
        if type(axis) == int or type(axis) == str:
            return [self._get_axis_name(axis)]
        if type(axis)==list or type(axis)==tuple:
            result = []
            for a in axis:
                result.append(self._get_axis_name(a))
            return result
        else:
            self.log.error('Can not parse axis : {}'.format(axis))

    def _get_axis_name(self, axis):
        """ Get an axis identifier (integer or name), and return axis name after checking axis is valid

        @param axis: axis id or name

        @return (str): Axis name
        """
        if type(axis) == str:
            if axis in self._axis_config:
                return axis
        if type(axis) == int:
            for name in self._axis_config:
                if self._axis_config[name]['id'] == axis:
                    return name
        # if still not found, we error
        self.log.error('Axis {} is not defined in config file'.format(axis))

    def _parse_result(self, axis, result):
        """ Take a valid axis input and list result and convert result to original format

        @param axis: a valid axis input
        @param result:  a list of result

        @return: result in the original format

        For example :
        'x' [1000] -> 10000
        ['x', 3] [0.5, 1.2] -> [0.5, 1.2]
        """
        if type(axis) == int or type(axis) == str:
            return result[0]
        if type(axis) == tuple:
            return tuple(result)
        else:
            return result

    def _get_config(self, axis, key):
        """ Get a value in axis config for a key for a given axis input and return with same format

        @param axis: A valid axis
        @param (str) key: the key requested

        @return the value for the axis in a similar format at the request

        """
        parsed_axis = self._parse_axis(axis)
        result = []
        for ax in parsed_axis:
            value = self._axis_config[ax][key]
            if type == list:  # protect mutable shallow array (ranges)
                result.append(tuple(value))
            else:
                result.append(value)
        return self._parse_result(axis, result)

    def _parse_value(self, axis, ax, value):
        """ For a given axis input and a given ax, return the value that make the most sense """
        if isinstance(value, (float, int)):  # a single number : we return it
            return value
        elif isinstance(value, (list, tuple)):  # an array
            if len(value) == 1:  # a single object in array : we return it
                return value[0]
            elif len(value) == len(axis):  # one to one correspondence with axis
                return value[axis.index(ax)]
            else:
                self.log.error('Could not set value for axis {}, value list length is incorrect')

    def _in_range(self, value, value_range, error_message=None):
        """ Check that a value is in range and eventually error of not """
        mini, maxi = value_range
        ok = mini <= value <= maxi
        if not ok and error_message is not None:
            self.log.error('{} - Value {} in not in range [{}, {}'.format(error_message, value, mini, maxi))
        return ok

    def enable_DC_input(self, axis):
        """ Enables the DC input for the given axis """
        parsed_axis = self._parse_axis(axis)
        for ax in parsed_axis:
            self._axis_config[ax]['dci'] = True

    def disable_DC_input(self, axis):
        """ Disables the DC input for the given axis """
        parsed_axis = self._parse_axis(axis)
        for ax in parsed_axis:
            self._axis_config[ax]['dci'] = False

    def get_DC_input_status(self, axis):
        """ Gets the status of the DC input for the given axis """
        return self._get_config(axis, 'dci')

    def ground(self):
        """ Set all axes to ground """
         parsed_axis = self._parse_axis(axis)
         for ax in parsed_axis:
            self._axis_config[ax]['grounded'] = True

    def unground(self):
        """ Set all axes to step mode """
        parsed_axis = self._parse_axis(axis)
        for ax in parsed_axis:
            self._axis_config[ax]['grounded'] = True
            
    def get_grounding_status(self, axis):
        """ Check whether the specified axes are grounded """
        return self._get_config(axis, 'grounded')

    def axis(self):
        """ Return a tuple of all axis identifiers """
        return tuple(self._axis_config.keys())

    def voltage_range(self, axis):
        """ Return the voltage range of one (or multiple) axis """
        return self._get_config(axis, 'voltage_range')

    def frequency_range(self, axis):
        """ Return the frequency range of one (or multiple) axis """
        return self._get_config(axis, 'frequency_range')

    def position_range(self, axis):
        """ Return the position range of one (or multiple) axis """
        return self._get_config(axis, 'position_range')

    def voltage(self, axis, value=None, buffered=False):
        """ Function that get or set the voltage of one ore multiple axis

        @param axis: axis input : 'x', 2, ['z', 3]...
        @param value: value for axis : 1.0, [1.0], [2.5, 2.8]...
        @param buffered: if set to True, just return the last read voltage without asking the controller

        @return: return the voltage of the axis with the same format than axis input
        """
        parsed_axis = self._parse_axis(axis)
        if value is not None:
            for ax in parsed_axis:
                new_value = self._parse_value(axis, ax, value)
                if self._in_range(new_value, self.voltage_range(ax), 'Voltage out of range'):
                    self._axis_config[ax]['voltage'] = new_value

        return self._get_config(axis, 'voltage')

    def frequency(self, axis, value=None, buffered=False):
        """ Function that get or set the frequency of one ore multiple axis

        @param axis: axis input : 'x', 2, ['z', 3]...
        @param value: value for axis : 100, [200], [500, 1000]...
        @param buffered: if set to True, just return the last read voltage without asking the controller

        @return: return the frequency of the axis with the same format than axis input
        """
        parsed_axis = self._parse_axis(axis)
        if value is not None:
            for ax in parsed_axis:
                new_value = int(self._parse_value(axis, ax, value))
                if self._in_range(new_value, self.frequency_range(ax), 'Frequency out of range'):
                    self._axis_config[ax]['frequency'] = new_value

        return self._get_config(axis, 'frequency')

    def capacitance(self, axis, buffered=False):
        """ Function that get the capacitance of one ore multiple axis

        @param axis: axis input : 'x', 2, ['z', 3]...
        @param buffered: buffered: if set to True, just return the last read capacitance without asking the controller
        will be None if never read
        """
        parsed_axis = self._parse_axis(axis)
        if not buffered:
            for ax in parsed_axis:
                self._axis_config[ax]['capacitance'] = 800e-9 + random.randrange(-100, 100) * 1e-9

        return self._get_config(axis, 'capacitance')

    def steps(self, axis, number):
        """ Function to do n (or n, m...) steps one one (or several) axis

        @param axis : 'x', 2, ['z', 3]...
        @param number: 100, [200], [500, 1000]...
        """
        parsed_axis = self._parse_axis(axis)
        for ax in parsed_axis:
            self.disable_DC_input(ax)
            number_step_axis = int(self._parse_value(axis, ax, number))
            if ax in ['x', 'y', 'z']:
                self._current_position[ax] += number_step_axis

    def stop(self, axis=None):
        """ Stop all movement on one, several or all (if None) axis"""
        self.log.info("All axis stopped")

# Motor interface

    def get_constraints(self):
        """ Retrieve the hardware constrains from the motor device. """

        constraints = {}

        axis_x = {}
        axis_x['label'] = 'x'
        axis_x['unit'] = 'm'
        axis_x['ramp'] = ['Linear']
        axis_x['pos_min'] = -1e5
        axis_x['pos_max'] = +1e5
        axis_x['pos_step'] = 1
        axis_x['vel_min'] = self.frequency_range('x')[0]
        axis_x['vel_max'] = self.frequency_range('x')[1]
        axis_x['vel_step'] = 1
        axis_x['acc_min'] = self.voltage_range('x')[0]
        axis_x['acc_max'] = self.voltage_range('x')[0]
        axis_x['acc_step'] = 1

        axis_y = {}
        axis_y['label'] = 'y'
        axis_y['unit'] = 'm'
        axis_y['ramp'] = ['Linear']
        axis_y['pos_min'] = -1e5
        axis_y['pos_max'] = +1e5  # that is basically the traveling range
        axis_y['pos_step'] = 1
        axis_y['vel_min'] = self.frequency_range('y')[0]
        axis_y['vel_max'] = self.frequency_range('y')[1]
        axis_y['vel_step'] = 1
        axis_y['acc_min'] = self.voltage_range('y')[0]
        axis_y['acc_max'] = self.voltage_range('y')[0]
        axis_y['acc_step'] = 1

        axis_z = {}
        axis_z['label'] = 'z'
        axis_z['unit'] = 'm'
        axis_z['ramp'] = ['Linear']
        axis_z['pos_min'] = -1e5
        axis_z['pos_max'] = +1e5
        axis_z['pos_step'] = 1
        axis_z['vel_min'] = self.frequency_range('z')[0]
        axis_z['vel_max'] = self.frequency_range('z')[1]
        axis_z['vel_step'] = 1
        axis_z['acc_min'] = self.voltage_range('z')[0]
        axis_z['acc_max'] = self.voltage_range('z')[0]
        axis_z['acc_step'] = 1

        constraints['x'] = axis_x
        constraints['y'] = axis_y
        constraints['z'] = axis_z

        return constraints

    def move_rel(self,  param_dict):
        """ Moves stage in given direction (relative movement)

        @param dict param_dict: dictionary, which passes all the relevant
                                parameters, which should be changed. Usage:
                                 {'axis_label': <the-abs-pos-value>}.
                                 'axis_label' must correspond to a label given
                                 to one of the axis.
        """
        for key in param_dict:
            if key in ['x', 'y', 'z']:
                self.steps(key, int(param_dict[key]))
        return 0

    def move_abs(self, param_dict):
        """ Moves stage to absolute position (absolute movement)
        """
        for key in param_dict:
            if key in ['x', 'y', 'z']:
                delta = param_dict[key] - self._current_position[key]
                self.move_rel({key: delta})

    def abort(self):
        """ Stops movement of the stage

        @return int: error code (0:OK, -1:error)
        """
        try:
            self.stop()
            return 0
        except:
            return -1

    def get_pos(self, param_list=None):
        """ Gets current position of the stage arms

        @param list param_list: optional, if a specific position of an axis
                                is desired, then the labels of the needed
                                axis should be passed in the param_list.
                                If nothing is passed, then from each axis the
                                position is asked.

        @return dict: with keys being the axis labels and item the current
                      position.
        """
        return self._current_position

    def get_status(self, param_list=None):
        """ Get the status of the position

        @param list param_list: optional, if a specific status of an axis
                                is desired, then the labels of the needed
                                axis should be passed in the param_list.
                                If nothing is passed, then from each axis the
                                status is asked.

        @return dict: with the axis label as key and the status number as item.
        """
        return {'x': 0, 'y': 0, 'z': 0}

    def calibrate(self, param_list=None):
        """ Calibrates the stage. """
        self._current_position = {'x': 0, 'y': 0, 'z': 0}
        return 0

    def get_velocity(self, param_list=None):
        """ Gets the current velocity for all connected axes.

        @param dict param_list: optional, if a specific velocity of an axis
                                is desired, then the labels of the needed
                                axis should be passed as the param_list.
                                If nothing is passed, then from each axis the
                                velocity is asked.

        @return dict : with the axis label as key and the velocity as item.
        """
        return {'x': self.frequency('x'),
                'y': self.frequency('y'),
                'z': self.frequency('z')}

    def set_velocity(self, param_dict):
        """ Write new value for velocity.

        @param dict param_dict: dictionary, which passes all the relevant
                                parameters, which should be changed. Usage:
                                 {'axis_label': <the-velocity-value>}.
                                 'axis_label' must correspond to a label given
                                 to one of the axis.

        @return int: error code (0:OK, -1:error)
        """
        for key in param_dict:
            if key in ['x', 'y', 'z']:
                self.frequency(key, param_dict[key])
# -*- coding: utf-8 -*-

"""
This file contains the hardware control of the motorized stage for Zaber

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
import serial
import struct
from collections import OrderedDict

from core.module import Base
from core.configoption import ConfigOption
from interface.motor_interface import MotorInterface


class MotorRotationZaber(Base, MotorInterface):
    """unstable: Christoph Müller, Simon Schmitt
    This is the Interface class to define the controls for the simple
    microwave hardware.

    Example config for copy-paste:

    motorstage_zaber:
        module.Class: 'motor.zaber_motor_rotation_stage.MotorRotationZaber'
        com_port: 'COM1'
        baud_rate: 9600
        timeout: 1000
        term_char: '\n'
        micro_step_size: 234.375e-6
        speed_conversion: 9.375
        axes:
            -   label: 'phi'
                id: 1
                angle_min: -10 # degrees
                angle_max: 10
                angle_step: 0.1
                velocity_min: 0.1 # degrees/s
                velocity_max: 5
                velocity_step: .1
            -   label: 'theta'
                id: 2
                angle_min: -10
                angle_max: 10
                angle_step: 0.1
                velocity_min: 0.1
                velocity_max: 5
                velocity_step: .1
    """

    _com_port = ConfigOption('com_port', 'COM1', missing='warn')
    _baud_rate = ConfigOption('baud_rate', 9600, missing='warn')
    _timeout = ConfigOption('timeout', 2000, missing='warn')
    _term_char = ConfigOption('term_char', '\n', missing='warn')
    _micro_step_size = ConfigOption('micro_step_size', 234.375e-6, missing='warn')
    _velocity_conversion = ConfigOption('speed_conversion', 9.375, missing='warn')

    _axes_conf = ConfigOption('axes', missing='error')
    _axes = dict()

    # see https://www.zaber.com/w/Manuals/Binary_Protocol_Manual
    # for full command set
    _cmd = {
            'home': 1,
            'move absolute': 20,
            'move relative': 21,
            'stop': 23,
            'set target speed': 42,
            'query': 53,
            'status': 54,
            'echo': 55,
            'return current position': 60
            }

    _status = {
                0: 'idle',
                1: 'executing home',
                10: 'manual move in progress',
                20: 'absolute move in progress',
                21: 'relative move in progress',
                22: 'constant speed motion',
                23: 'stopping'
                }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        for axis in self._axes_conf:
            self._axes[axis['label']] = axis

    def on_activate(self):
        """ Initialisation performed during activation of the module.
        """

        self._serial_connection = serial.Serial(
            port=self._com_port,
            baudrate=self._baud_rate,
            bytesize=8,
            parity='N',
            stopbits=1,
            timeout=self._timeout)

        return 0


    def on_deactivate(self):
        """ Deinitialisation performed during deactivation of the module.
        """
        self._serial_connection.close()
        return 0


    def get_constraints(self):
        """ Retrieve the hardware constrains from the motor device.

        @return dict: dict with constraints for the sequence generation and GUI

        Provides all the constraints for the xyz stage  and rot stage (like total
        movement, velocity, ...)
        Each constraint is a tuple of the form
            (min_value, max_value, stepsize)
        """
        constraints = OrderedDict()
        for axis, params in self._axes.items():
            constraints[axis] = {'label': axis,
                                 'ID': params['id'],
                                 'pos_min': params['angle_min'],
                                 'pos_max': params['angle_max'],
                                 'pos_step': params['angle_step'],
                                 'vel_min': params['velocity_min'],
                                 'vel_max': params['velocity_max'],
                                 'vel_step': params['velocity_step'],
                                 'unit': '°',
                                 'ramp': None,
                                 'acc_min': None,
                                 'acc_max': None,
                                 'acc_step': None}

        return constraints

    def ping(self, axis):
        response = self._ask(axis, 'echo', 555)
        return response == 555

    def move_rel(self, param_dict):
        """Moves stage by a given angle (relative movement)

        @param dict param_dict: Dictionary with axis name and relative movement in deg

        @return dict velocity: Dictionary with axis name and final position in deg
        """
        pos = {}
        try:
            for axis_label, angle in param_dict.items():
                if abs(angle) >= self._micro_step_size:
                    steps = int(angle / self._micro_step_size)
                    pos[axis_label] = self._ask(axis_label, 'move relative', steps) * self._micro_step_size
                else:
                    self.log.warning('Desired step "{0}" is too small. Minimum is "{1}"'.format(angle,
                                                                                                self._micro_step_size))
                    pos = self.get_pos(list(param_dict.keys()))
        except:
            self.log.error('relative movement of zaber rotation stage is not possible')
            pos = self.get_pos(list(param_dict.keys()))
        return pos

    def move_abs(self, param_dict):
        """Moves stage to an absolute angle (absolute movement)

        @param dict param_dict: Dictionary with axis name and target position in deg

        @return dict velocity: Dictionary with axis name and final position in deg
        """
        pos = {}
        try:
            for axis_label, angle in param_dict.items():
                steps = int(angle / self._micro_step_size)
                pos[axis_label] = self._ask(axis_label, 'move absolute', steps) * self._micro_step_size
        except:
            self.log.error('absolute movement of zaber rotation stage is not possible')
            pos = self.get_pos(list(param_dict.keys()))
        return pos

    def axes(self):
        return list(self._axes.keys())

    def abort(self):
        """Stops movement of the stage

        @return int: error code (0:OK, -1:error)
        """
        try:
            for axis in self.axes():
                self._send_command(axis, 'stop', 0)
            while not self._motors_stopped():
                time.sleep(0.2)
            return 0
        except:
            self.log.error('ROTATIONAL MOVEMENT NOT STOPPED!!!)')
            return -1

    def get_pos(self,param_list=None):
        """ Gets current position of the rotation stage

        @param list param_list: List with axis name

        @return dict pos: Dictionary with axis name and pos in deg    """
        try:
            pos = {}
            axis_list = param_list if param_list is not None else self.axes()
            for axis_label in axis_list:
                pos[axis_label] = self._ask(axis_label, 'return current position', 0) * self._micro_step_size
            return pos
        except:
            self.log.error('Cannot find position of zaber-rotation-stage')
            return -1

    def get_status(self,param_list=None):
        """ Get the status of the position

        @param list param_list: optional, if a specific status of an axis
                                is desired, then the labels of the needed
                                axis should be passed in the param_list.
                                If nothing is passed, then from each axis the
                                status is asked.

        @return dict status:   · 0 - idle, not currently executing any instructions
                        · 1 - executing a home instruction
                        · 10 - executing a manual move (i.e. the manual control knob is turned)
                        · 20 - executing a move absolute instruction
                        · 21 - executing a move relative instruction
                        · 22 - executing a move at constant speed instruction
                        · 23 - executing a stop instruction (i.e. decelerating)
                                """
        status = {}
        axis_list = param_list if param_list is not None else self.axes()

        try:
            for axis_label in axis_list:
                status[axis_label] = self._ask(axis_label, 'status', 0)
            return status
        except:
            self.log.error('Could not get status')
            return -1

    def status_decode(self, status):
        msg = {}
        for axis, code in status.items():
            msg[axis] = self._status[code] if code in self._status else 'Unknown code: {}'.format(code)
        return msg

    def get_status_decoded(self, param_list=None):
        return self.status_decode(self.get_status(param_list))

    def calibrate(self, param_list=None):
        """ Calibrates the rotation motor

        @param list param_list: Dictionary with axis name

        @return dict pos: Dictionary with axis name and pos in deg
        """
        axis_list = param_list if param_list is not None else self.axes()
        pos = {}
        try:
            for axis_label in axis_list:
                pos[axis_label] = self._ask(axis_label, 'home', 0) * self._micro_step_size
        except:
            self.log.error('Could not calibrate zaber rotation stage!')
            pos = self.get_pos()
        return pos


    def get_velocity(self, param_list=None):
        """ Asks current value for velocity.

        @param list param_list: Dictionary with axis name

        @return dict velocity: Dictionary with axis name and velocity in deg/s
        """
        axis_list = param_list if param_list is not None else self.axes()
        velocity = {}
        try:
            for axis_label in axis_list:
                velocity[axis_label] = self._ask(axis_label, 'query', self._cmd['set target speed']) * self._micro_step_size
            return velocity
        except:
            self.log.error('Could not set rotational velocity')
            return -1

    def set_velocity(self, param_dict):
        """ Write new value for velocity.

        @param dict param_dict: Dictionary with axis name and target velocity in deg/s

        @return dict velocity: Dictionary with axis name and target velocity in deg/s
        """
        velocity = {}
        try:
            for axis_label, speed in param_dict.items():
                if speed <= self._max_vel:
                    speed = int(speed/self.velocity_conversion/self._micro_step_size)
                    speed_set = self._ask(axis_label, 'set target speed', speed);
                    velocity[axis_label] = speed_set * self._velocity_conversion * self._micro_step_size
                else:
                    self.log.warning('Desired velocity "{0}" is too high. Maximum is "{1}"'
                                     .format(velocity, self._max_vel))
                    velocity = self.get_velocity()
        except:
            self.log.error('Could not set rotational velocity')
            velocity = self.get_velocity()
        return velocity

########################## internal methods ##################################

    def _send_command(self, axis, command, data):
        try:
            axis_no = self._axes[axis]['id']
            cmd_no = self._cmd[command]
            self._send_raw_command(axis_no, cmd_no, data)
        except KeyError as ke:
            self.log.error("Failed to send command - missing {}".format(ke))

    def _send_raw_command(self, axis_no, cmd_no, data):
        try:
            msg = struct.pack('<BBl', axis_no, cmd_no, data)
            self._serial_connection.write(msg)
            self.log.debug('Sending command {} {} {} as {}'.format(axis_no, cmd_no, data, msg.hex()))
        except serial.SerialException as se:
            self.log.error("Failed to send command {}".format(se))

    def _read_response(self):
        response = bytearray([0] * 6)
        try:
            self._serial_connection.readinto(response)
            (axis_no, cmd_ret, data) = struct.unpack('<BBl', response)
            self.log.debug('Received {} unpacked as {} {} {}'.format(response.hex(), axis_no, cmd_ret, data))
            return axis_no, cmd_ret, data
        except serial.SerialException as se:
            self.log.error("Failed to read response: {}".format(se))
        except Exception as e:
            self.log.error("Failed to decode response {} {}".format(response.hex(), e))

    def _ask(self, axis, command, data):
        self._send_command(axis, command, data)
        r_axis, status, response = self._read_response()
        if r_axis != self._axes[axis]['id']:
            self.log.error('Response was for the wrong axis')
        elif status == 0xff:
            self.log.error('Zaber replied with an error')
        else:
            return response

    def _motor_stopped(self):
        """checks if the rotation stage is still moving
        @return: bool stopped: True if motor is not moving, False otherwise"""

        moving = False
        for axis, code in self.get_status().items():
            if code != 0:
                moving = True
        return not moving


# -*- coding: utf-8 -*-

"""
This module contains the Qudi Hardware module attocube ANC300 .

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

import telnetlib
import time
import re

from core.module import Base, ConfigOption
from interface.piezo_stepper_interface import PiezoStepperInterface

class Anc300(Base, PiezoStepperInterface):
    """ 
    """

    _modtype = 'Anc300'
    _modclass = 'hardware'

    _host = ConfigOption('host', missing='error')
    _password = ConfigOption('password', b"123456", missing='warn')
    _control_port = ConfigOption('port', 7230, missing='warn')
    _lua_port = ConfigOption('lua_port', 7231, missing='warn')
    _axes = ConfigOption('axes', {}, missing='error')
    _offset_list = ConfigOption('offset_list', {}, missing='warn')

    _control_connection = None
    _lua_connection = None

    _voltage_range_default = [0, 60]
    _frequency_range_default = [1, 500]
    _voltage_range = _voltage_range_default
    _frequency_range = _frequency_range_default
    _axis_offset = dict()   # this stored state is never actually used. Set as a side effect
    _axis_voltage = dict()
    _axis_frequency = dict()

    _attocube_modes = {"step": "stp",
                       "ground": "gnd",
                       "input": "inp",
                       "offset": "off"}

    _attocube_lua_modes = {"step": "STP",
                           "ground": "GND",
                           "input": "INP",
                           "offset": "OSV"}


    # functions to load when connected to the lua port
    # hampered slightly by limited buffer and newline sensitivity
    # Arrays in V of the form {12.345678,...} are ok up to at least 100 values
    # Append arrays if necessary with append
    _lua_functions = [
        'require "io"',
        'require "os"',
        'ok = 1',
        ('function trigger() '  # Cause DTR line on serial port to go high, triggering acquisition (via electronics)
            'local f = io.open("/dev/ttyS2","w"); '
            'f:write(" "); '
            'f:close(); '
            'end'),
        'function dir(d) for i in io.popen("ls " .. d):lines() do print(i) end end',
        'function run(x) for i in io.popen(x):lines() do print(i) end end',
        'function busywait(t) local n = math.ceil(t / 1.42e-3); for i = 0,n do end end',  # estimated, in ms
        'function setOffset(axis,v) axis.mode=OSV; axis.osv=v end',
        'function setMode(axis,mode) axis.mode = mode end',
        'function append(x,y) offset=#x for i,v in pairs(y) do x[offset+i] = v end end',  # append two arrays
        's=0.2',
        ('function setOffsetSmoothly(axis,v) '
           'while s < axis.osv - v do axis.osv = axis.osv - s  end '  # adjust smoothly without a jump at ~ 10V/150us
           'while axis.osv - v < -s do axis.osv = axis.osv + s end '
           'axis.osv = v; '
         'end'),
        ('function scan(axis,list,delay) '
           'oldmode = axis.mode; '
           'oldv = axis.osv; '
           'axis.mode = OSV; '
           'setOffsetSmoothly(axis,list[1]); '
           'for i,v in ipairs(list) do '
             'setOffsetSmoothly(axis,v); '
             'trigger(); '
             'busywait(delay); '
           'end '
           'trigger(); '
           'axis.mode = oldmode; '
           'setOffsetSmoothly(axis,oldv); '
         'end')]

    def on_activate(self):
        """ Initialisation performed during activation of the module.

        @param object e: Event class object from Fysom.
                         An object created by the state machine module Fysom,
                         which is connected to a specific event (have a look in
                         the Base Class). This object contains the passed event,
                         the state before the event happened and the destination
                         of the state which should be reached after the event
                         had happened.
        """
        config = self.getConfiguration()

        # some default values for the hardware:
        # Todo: This needs to be calculated by a more complicated formula depnding on the measured capacitance.
        # Todo: voltage range should be defined for each axis, the same for frequency

        if 'voltage_range' in config.keys():
            if float(config['voltage_range'][0]) < float(
                    config['voltage_range'][1]):
                self._voltage_range = [float(config['voltage_range'][0]),
                                               float(config['voltage_range'][1])]
            else:
                self._voltage_range = self._voltage_range_default
                self.log.warning(
                    'Configuration ({}) of voltage_range incorrect, taking [0,60] instead.'
                    ''.format(config['voltage_range']))
        else:
            self.log.warning('No voltage_range configured taking [0,60] instead.')
            self._voltage_range = self._voltage_range_default

        # strictly should be dependent on the capacitance on each axis, but with a conservative
        # range a common limit should be fine and allow plenty speed
        if 'frequency_range' in config.keys():
            if float(config['frequency_range'][0]) < float(
                    config['frequency_range'][1]):
                self._frequency_range = [float(config['frequency_range'][0]),
                                               float(config['frequency_range'][1])]
            else:
                self._frequency_range = self._frequency_range_default
                self.log.warning(
                    'Configuration ({}) of frequency_range incorrect, taking [1,500] instead.'
                    ''.format(config['frequency_range']))
        else:
            self.log.warning('No frequency_range configured taking [1,500] instead.')
            self._frequency_range = self._frequency_range_default

        # connect Ethernet socket and FTP
        self._control_connection = self._connect(self._control_port)
        self._lua_connection = self._connect(self._lua_port)
        self.load_lua_functions()

        self._initalize_axis()
        # This reads all the values from the hardware and checks if values ly inside defined boundaries
        self._get_all_hardwaresettings()

    def load_lua_functions(self):

        # check if they're already loaded
        err, msg = self._send_lua_cmd('print(ok)', read=True, checkLoaded=False)
        self.log.info("Lua functions ok? '{0}' '{1}' '{2}'".format(err, len(msg), msg[-2]))
        if err == 0 and len(msg) >= 2 and msg[-2] == '1':
            return
        else:
            self.log.info("Reloading Lua functions")

        # Load Lua functions and variables
        for cmd in self._lua_functions:
            err, msg = self._send_lua_cmd(cmd, read=False, checkLoaded=False)
            if err != 0:
                self.log.error("Lua function load error loading {}:\n{}".format(cmd, msg))
        for name, offsets in self._offset_list.items():  # set as a Lua variable 'name'
            cmd = name + "={" + ",".join(map(lambda x: "%.5f" % x, offsets)) + "}"
            rc, msg = self._send_lua_cmd(cmd, read=False, checkLoaded=False)
            if rc != 0:
                self.log.error("Loading offset_lists failed {}".format(msg))

        return

    def on_deactivate(self):
        """ Deinitialisation performed during deactivation of the module.
        """
        self._control_connection.close()
        self._lua_connection.close()

    # =================== Attocube Communication ========================
    # Todo: make two send cmd, one with return value, one without
    def _send_cmd(self, cmd, expected_response="OK", read=False):
        """Sends a command to the attocube steppers and checks response value

        @param str cmd: Attocube ANC300 command
        @param list(str) expected_response: expected attocube response to command as list per 
        expected line
        @param bool read: if True actually checks for expected result, else only checks for "OK"
        
        @return int: error code (0: OK, -1:error)
        """
        full_cmd = cmd.encode('ascii') + b"\r\n"  # converting to binary
        self._control_connection.read_eager()  # disregard old print outs
        self._control_connection.write(full_cmd)  # send command
        # any response ends with ">" from the attocube. Therefore connection waits until this happened
        try:
            value_binary = self._control_connection.read_until(b">", timeout=1)
        except:
            self.log.error("time out of telnet connection attocube did not respond")
            return -1

        # transform into string and split at any sequence of LF/CR/CRLF - sometimes the ANC300 omits one
        value = re.split("[\r\n]+", value_binary.decode())
        if value[-2] == "ERROR":
            if read:
                return -1, value
            self.log.warning('The command {} did not work but produced an {}'.format(value[-3],
                                                                                     value[-2]))
            return -1
        elif value == expected_response and read:
            return 0, value
        elif value[-2] == "OK":
            if read:
                return 0, value
            return 0
        return -1, value

    def _send_lua_cmd(self, cmd, read=False, checkLoaded=True):
        """Sends a Lua command to the attocube steppers on the other port and checks response value

        @param str cmd: Attocube ANC300 Lua code
        @param bool read: if True read until the prompt & return the response unless there's an error

        @return (int,str list): error code (0: OK, -1:error), response
        """

        if checkLoaded:
            self.load_lua_functions()

        full_cmd = cmd.encode('ascii') + b"\r\n"  # converting to binary
        self._lua_connection.read_eager()  # disregard old print outs
        self._lua_connection.write(full_cmd)  # send command
        # any response ends with ">" from the attocube. Therefore connection waits until this happened
        try:
            value_binary = self._lua_connection.read_until(b">", timeout=1)
        except:
            self.log.error("time out of telnet connection attocube did not respond")
            return -1, []

        # transform into string and split at any sequence of LF/CR/CRLF - sometimes the ANC300 omits one
        output = value_binary.decode()
        self.log.info("Lua response: '{}'".format(output))
        value = re.split("[\r\n]+", output)
        if len(value) > 1 and value[-2].startswith("ERROR"):
            if read:
                return -1, value
            self.log.warning('The command {} did not work but responded {}'.format(full_cmd, value[-2]))
            return -1, value
        else:
            if read:
                return 0, value
            return 0, []

    def _send_cmd_silent(self, cmd):
        """Sends a command to the attocube steppers and without checking the response. +
        Only use, when quick execution is necessary. Always returns 0. It saves at least 30ms (
        response time ANC300) per call

        @param str cmd: Attocube ANC300 command
        """
        full_cmd = cmd.encode('ascii') + b"\r\n"  # converting to binary
        self._control_connection.read_eager()  # disregard old print outs
        self._control_connection.write(full_cmd)  # send command
        self._control_connection.read_eager()
        return 0

    def _connect(self, port):
        counter = 0
        connected = False
        tn = telnetlib.Telnet(self._host, port)
        tn.open(self._host, port)
        password_enc = str(self._password).encode('ascii')
        while not connected:
            if counter > 7:
                self.log.error('Connection to attocube could not be established.\n'
                               'Check password, physical connection, host etc. and try again.')
                break
            tn.read_until(b"Authorization code: ")
            tn.write(password_enc + b"\n")
            time.sleep(0.1)  # the ANC300 needs time to answer
            value_binary = tn.read_very_eager()
            value = value_binary.decode().split()
            if value[2] == 'success':  # Checks if connection was successful
                connected = True
                # Todo: Check how to do correct log messages
                self.log.info("Connection to Attocube was established")
            else:
                counter += 1
        tn.read_very_eager()
        return tn

    # =================== General Methods ==========================================

    def set_step_voltage(self, axis, voltage):
        """Sets the step voltage/amplitude for axis for the ANC300

        @param str axis: key of the dictionary self._axes for the axis to be changed
        @param float voltage: the stepping amplitude/voltage the axis should be set to
        @return int: error code (0:OK, -1:error)
        """

        if voltage is None:
            return 0  # Why would you do this?

        if voltage < self._voltage_range[0] or voltage > self._voltage_range[1]:
            self.log.error(
                'Voltage {0} on axis {1} exceeds the permitted range.'.format(voltage, axis))
            return -1
        elif axis in self._axes.keys():
            command = "setv {} {}".format(self._axes[axis], voltage)
            self._axis_voltage[axis] = voltage
            return self._send_cmd(command)
        else:
            self.log.error("axis {} not in list of possible axes".format(self._axes))
            return -1

    def get_step_voltage(self, axis):
        """ Gets the voltage of a step for a specific axis

        @param str axis: the axis for which the step amplitude is to be checked
        @return float: the step amplitude of the axis
        """
        if axis in self._axes.keys():
            command = "getv {}".format(self._axes[axis])
            result = self._send_cmd(command, read=True)
            if result[0] == -1:
                return -1
            voltage_line = result[1][-3].split()
            self._axis_voltage[axis] = float(voltage_line[-2])
            if self._voltage_range[0] > self._axis_voltage[axis] or self._axis_voltage[axis] > self._voltage_range[1]:
                self.log.error(
                    "The voltage of {} V of axis {} in the ANC300 lies outside the defined range{},{]".format(
                        self._axis_voltage[axis], axis, self._voltage_range[0], self._voltage_range[1]))
            return self._axis_voltage[axis]
        self.log.error("axis {} not in list of possible axes".format(self._axes))
        return -1
        # Todo: Do better error handling

    def set_step_frequency(self, axis, freq=None):
        """Sets the step frequency for axis for the ANC300

        @param str axis: key of the dictionary self._axes for the axis to be changed
        @param float freq: the stepping frequency the axis should be set to
        @return int: error code (0:OK, -1:error)
        """
        # Todo this need to have a check added if freq is inside freq range
        # Todo I need to add decide how to save the freq for the three axis and if decided update the current freq

        if freq is not None:
            if axis in self._axes.keys():
                command = "setf {} {}".format(self._axes[axis], freq)
                # command = "setf " + self._axes[axis] + " " + str(freq)
                self._axis_frequency[axis] = freq
                return self._send_cmd(command)
            self.log.error("axis {} not in list of possible axes".format(self._axes))
            return -1
        self.log.info("No frequency was given so the step frequency was not changed.")
        return 0

    def get_step_frequency(self, axis):
        """ Gets the step frequency for a specific axis

        @param str axis: the axis for which the frequency is to be checked
        @return float: the step frequency of the axis
        """
        if axis in self._axes.keys():
            command = "getf {}".format(self._axes[axis])
            result = self._send_cmd(command, read=True)
            if result[0] == -1:
                return -1
            else:
                frequency_line = result[1][-3].split()
            self._axis_frequency[axis] = float(frequency_line[-2])
            if self._frequency_range[0] > self._axis_frequency[axis]\
               or self._axis_frequency[axis] > self._frequency_range[1]:
                self.log.error(
                    "The value of {} V of axis {} in the ANC300 lies outside the defined range{},{]".format(
                        self._axis_frequency[axis], axis, self._frequency_range[0],
                        self._frequency_range[1]))
            return self._axis_frequency[axis]
        self.log.error("axis {} not in list of possible axes {}".format(axis, self._axes))
        return -1

    def _lua_axis(self, axis):
        return "m" + str(self._axes[axis])

    def set_axis_mode(self, axis, mode):
        """Changes Attocube axis mode

        @param str axis: axis to be changed, can only be part of dictionary axes
        @param str mode: mode to be set
        @return int: error code (0: OK, -1:error)
        """
        # Todo: why create other strings you can't look up in the manual & translate?
        if mode in self._attocube_modes.keys():
            if axis in self._axes.keys():
                attocube_mode = self._attocube_lua_modes[mode]
                command = "setOffset({},{})".format(self._lua_axis(axis), attocube_mode)
                result, msg = self._send_lua_cmd(command)  # some modes can only be set via the lua port
                if result == 0:
                    self._axis_mode[axis] = mode
                    return 0
                else:
                    self.log.error("Setting axis {} to mode {} failed: {}".format(self._axes[axis], mode, msg))
            else:
                self.log.error("axis {} not in list of possible axes {}".format(axis, self._axes))
                return -1
        else:
            self.log.error("mode {} not in list of possible modes".format(mode))
            return -1

    def get_axis_mode(self, axis):
        """ Gets the mode for a specific axis

        @param str axis: the axis for which the mode is to be checked
        @return float: the mode of the axis, -1 for error
        """
        if axis in self._axes.keys():
            command = "getm {}".format(self._axes[axis])
            result = self._send_cmd(command, read=True)  # All modes can be read with the control port
            if result[0] == -1:
                return -1
            mode_line = result[1][-3].split()
            for mode, attocube_mode in self._attocube_modes.items():
                if attocube_mode == mode_line[-1]:
                    self._axis_mode[axis] = mode
                    return self._axis_mode[axis]
            else:
                self.log.error("Current mode of controller {} not in list of modes{}"
                               .format(mode_line[-1], self._attocube_modes))
                return -1
        self.log.error("axis {} not in list of possible axes".format(self._axes))
        return -1

    def get_offset(self, axis):
        """ Gets the offset voltage for a specific axis

        @param str axis: the axis for which the frequency is to be checked
        @return float: the offset voltage of the axis
        """
        if axis in self._axes.keys():
            command = "geta {}".format(self._axes[axis])
            result = self._send_cmd(command, read=True)
            if result[0] == -1:
                return -1
            else:
                offset_line = result[1][-3].split()
            self._axis_offset[axis] = float(offset_line[-2])
            if self._voltage_range[0] > self._axis_offset[axis] or self._axis_offset[axis] > self._voltage_range[1]:
                self.log.error(
                        "The offset of {} V of axis {} in the ANC300 lies outside the defined range{},{]"
                        .format(self._axis_offset[axis], axis, self._voltage_range[0],self._voltage_range[1]))
            return self._axis_offset[axis]
        self.log.error("axis {} not in list of possible axes {}".format(axis, self._axes))
        return -1

    def set_offset(self, axis, voltage):
        """Changes Attocube axis offset

        @param str axis: axis to be changed, can only be part of dictionary axes
        @param str voltage: offset to be set (implicitly changing to offset mode if required)
        @return int: error code (0: OK, -1:error)
        """
        if self.get_axis_mode(axis) != "offset":
            self.log.warn('Implicitly changing axis {} into offset mode'.format(axis))

        if voltage is None:
            return 0  # Why would you do this?

        if voltage < self._voltage_range[0] or voltage > self._voltage_range[1]:
            self.log.error('Offset voltage {0} exceeds the permitted range.'.format(voltage))
            return -1
        elif axis in self._axes:
            command = "setOffsetSmoothly({},{})".format(self._lua_axis(axis), voltage)
            self._axis_offset[axis] = voltage
            rc, msg = self._send_lua_cmd(command)
            return rc
        else:
            self.log.error("axis {} not in list of possible axes".format(self._axes))
            return -1

    def scan_offset(self, axis, offset_list, dwell):
        """Scans Attocube axis offset

        @param str axis: axis to be scanned, can only be part of dictionary axes
        @param str offset_list: preconfigured list of offsets to visit
        @param float dwell: time to sit on each point for approximately in ms
        @return int: error code (0: OK, -1:error)
        """
        if axis not in self._axes:
            self.log.error("axis {} not in list of possible axes".format(self._axes))
            return -1
        elif offset_list not in self._offset_list:
            self.log.error("offset list {} not in configuration".format(offset_list))
            return -1
        else:
            command = "scan({},{},{})".format(self._lua_axis(axis), offset_list, dwell)
            rc, msg = self._send_lua_cmd(command)
            return rc

    def set_DC_in(self, axis, on):
        """Changes Attocube axis DC input status

        @param str axis: axis to be changed, can only be part of dictionary axes
        @param bool on: if True is turned on, False is turned off
        @return int: error code (0: OK, -1:error)
        """
        if axis in self._axes.keys():
            if on:
                dci = "on"
            else:
                dci = "off"
            command = "setdci {} ".format(self._axes[axis]) + dci
            result = self._send_cmd(command)
            if result == 0:
                self._axis_dci[axis] = dci
                return 0
            else:
                return -1
        self.log.error("axis {} not in list of possible axes".format(self._axes))
        return -1

    def get_DC_in(self, axis):
        """ Checks the status of the DC input for a specific axis

        @param str axis: the axis for which the input is to be checked
        @return bool: True for on, False for off, -1 for error
        """
        if axis in self._axes.keys():
            command = "getdci {}".format(self._axes[axis])
            result = self._send_cmd(command, read=True)
            if result[0] == -1:
                return -1
            dci_result = result[1][-3].split()
            self._axis_dci[axis] = dci_result[-1]
            if dci_result[-1] == "off":
                return False
            return True
        self.log.error("axis {} not in list of possible axes".format(self._axes))
        return -1

    def set_AC_in(self, axis, on):
        """Changes Attocube axis DC input status

        @param str axis: axis to be changed, can only be part of dictionary axes
        @param bool on: if True is turned on, False is turned off
        @return int: error code (0: OK, -1:error)
        """
        if axis in self._axes.keys():
            if on:
                aci = "on"
            else:
                aci = "off"
            command = "setdci {} ".format(self._axes[axis]) + aci
            result = self._send_cmd(command)
            if result == 0:
                self._axis_aci[axis] = aci
                return 0
            else:
                return -1
        self.log.error("axis {} not in list of possible axes".format(self._axes))
        return -1

    def get_AC_in(self, axis):
        """ Checks the status of the AC input for a specific axis

        @param str axis: the axis for which the input is to be checked
        @return bool: True for on, False for off, -1 for error
        """
        if axis in self._axes.keys():
            command = "getaci {}".format(self._axes[axis])
            result = self._send_cmd(command, read=True)
            if result[0] == -1:
                return -1
            aci_result = result[1][-3].split()
            self._axis_aci[axis] = aci_result[-1]
            if aci_result[-1] == "off":
                return False
            return True
        self.log.error("axis {} not in list of possible axes".format(self._axes))
        return -1

    def _get_all_hardwaresettings(self):
        axis = self.get_stepper_axes()
        for i in self._axes.keys():  # get all axis names
            if axis[self._axes[i] - 1]:  # check it the axis actually exists
                self.get_step_voltage(i)
                self.get_step_frequency(i)
                self.get_axis_mode(i)

            else:
                self.log.error("axis {} was specified as number {} on ANC300\n  but this axis "
                               "doesn't exist in the ANC300".format(i, self._axes[i]))
                return -1
        else:
            return 0

    def _initalize_axis(self):
        """ Initialises all axes values, setting them to 0.
        This should only be called when making a new instance.
        """
        axis = self.get_stepper_axes()
        self._axis_voltage = {}
        self._axis_frequency = {}
        self._axis_mode = {}

        for i in self._axes.keys():  # get all axis names
            if axis[self._axes[i] - 1]:  # check it the axis actually exists
                self._axis_voltage[i] = 0
                self._axis_frequency[i] = 0
                self._axis_mode[i] = ""
            else:
                self.log.error("axis {} was specified as number {} on ANC300\n  but this axis "
                               "doesn't exist in the ANC300".format(i, self._axes[i]))

    # =================== ConfocalStepperInterface Commands ========================
    def reset_hardware(self):
        """ Resets the hardware, so the connection is lost and other programs
            can access it.

        @return int: error code (0:OK, -1:error)
        """
        self.log.warning('Attocube Device does not need to be reset.')
        pass

    def get_voltage_range(self, axis):
        """Returns the current possible stepping voltage range of the stepping device for all axes

        @return list: voltage range of scanner
        """
        return self._voltage_range

    def get_frequency_range(self, axis):
        """Returns the current possible stepping frequency range of the stepping device for all axes
        @return list: voltage range of scanner
        """
        return self._frequency_range

    # Todo: It might make sense to return a library of axis ("x", "y", "z" etc. against booleans) check.
    def get_stepper_axes(self):
        """"
        Checks which axes of the hardware have a reaction by the hardware

         @return list: list of booleans for each possible axis, if true axis exists

         On error, return empty list
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

    def _step(self, command, axis, steps=1):

        if axis in self._axes.keys():
            if self._axis_mode[axis] != 'step':
                self.log.warning("Set mode to stepping. Current mode {}.".format(self.get_axis_mode(axis)))
                return -1
                # TODO still needs to decide if necessary to use send_cmd or if silent_cmd is sufficient,
                #  or if option in call. Also needs to check response from attocube if moved.
            return self._send_cmd("{} {} {}".format(command, self._axes[axis], steps))
        else:
            self.log.error("axis {} not in list of possible axes".format(self._axes))
            return -1

    def _step_continuously(self, command, axis):

        if axis in self._axes.keys():
            if self._axis_mode[axis] != 'step':
                self.log.warning("Set mode to stepping. Current mode {}.".format(self.get_axis_mode(axis)))
                return -1
                # TODO still needs to decide if necessary to use send_cmd or if silent_cmd is sufficient,
                #  or if option in call. Also needs to check response from attocube if moved.
            return self._send_cmd("{} {} c".format(command, self._axes[axis]))
        else:
            self.log.error("axis {} not in list of possible axes".format(self._axes))
            return -1

    def step_up(self, axis, steps=1):
        """Moves axis up by a number of steps

        @param str axis: axis to be moved, can only be part of dictionary axes
        @param int steps: number of steps to be moved
        @return int:  error code (0: OK, -1:error)
        """
        return self._step("stepu",axis,steps)

    def step_down(self, axis, steps=1):
        """Moves axis down by a number of steps

        @param str axis: axis to be moved, can only be part of dictionary axes
        @param int steps: number of steps to be moved
        @return int:  error code (0: OK, -1:error)
        """
        return self._step("stepd", axis, steps)

    def step_up_continuously(self, axis):
        """Moves axis up until stopped

        @param str axis: axis to be moved, can only be part of dictionary axes
        @return int:  error code (0: OK, -1:error)
        """
        return self._step_continuously("stepu", axis)

    def step_down_continuously(self, axis):
        """Moves axis up until stopped

        @param str axis: axis to be moved, can only be part of dictionary axes
        @return int:  error code (0: OK, -1:error)
        """
        return self._step_continuously("stepd", axis)

    def stop_axis(self, axis):
        """Stops motion on specified axis,
        only necessary if stepping in continuous mode

        @param str axis: axis to be moved, can only be part of dictionary axes
        @return int: error code (0: OK, -1:error)
        """
        if axis in self._axes.keys():
            command = "stop {}".format(self._axes[axis])
            return self._send_cmd(command)
        else:
            self.log.error("axis {} not in list of possible axes".format(self._axes))
            return -1

    def stop_all_axes(self):
        """Stops motion on all configured axes

        @return 0
        """

        for axis in self._axes:
            self.stop_axis(axis)

        self.log.info("any attocube stepper motion has been stopped")
        return 0

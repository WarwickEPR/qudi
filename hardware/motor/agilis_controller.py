# -*- coding: utf-8 -*-
"""
This module controls Newport Agilis Controller (AG-UC8).

DISCLAIMER:
===========
This was written initially for controlling PR100 rotation mounts
which do not contain a limit switch and hence not possible to read current position
using the controller. Therefore, this implements a psuedo-closed-loop approach to
maintaining position of the PR100 rotation mount.

- P. L. Diggle
===========

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
from core.module import Base, ConfigOption
import visa
from interface.motor_interface import MotorInterface
import re

class AgilisMotor():
    """ This is the Interface class to define the controls for the simple
        step motor device. The actual hardware implementation might have a
        different amount of axis. Implement each single axis as 'private'
        methods for the hardware class, which get called by the general method.
    """

    def __init__(self, motor_type, channel, axis, label, unit, pos_pitch, neg_pitch, constraints, start_pos):
        self._type = motor_type
        self._channel = channel
        self._axis = axis
        self.label = label
        self.unit = unit
        self.calibration = [pos_pitch, neg_pitch]
        self._constraints = constraints
        self._constraints['pos_step'] = 0.1
        self._start_pos = start_pos

        self._current_position = 0
        # Make sure we've got the correct starting position based on whether we can read it or not
        self.set_current_position()

    def set_current_position(self):
        if self._type == "PR100":
            # Psuedo-closed-loop so need to read last stored position
            self._current_position = self._start_pos
        else:
            # Assume otherwise it can be read
            self._current_position = 0

    def get_constraints(self):
        return self._constraints

    def set_move_rel(self,  rel_distance):
        self._current_position += rel_distance

    def set_move_abs(self, abs_distance):
        self._current_position += abs_distance

    def get_current_position(self):
        if self._current_position == 360 or self.get_current_position == -360:
            self._current_position = 0
            return self.get_current_position
        else:
            return self._current_position

    def abort(self, target_distance, abort_distance):
        self._current_position = self._current_position - target_distance + abort_distance

    def convert_to_step(self, distance):
        """ Convert the input to steps the motor needs to take

        Forward (pos) and backward (neg) pitch are different (from manual)
        Therefore need to calculate conversion for forward and backward motion
        """

        if self.unit == 'degrees':
            if distance < 0:
                # do conversion for neg direction, based on backwards calibration and give integer
                return int(round(distance * self.calibration[1]))
            elif distance > 0:
                # do conversion for pos direction, based on forwards calibration and give integer
                return int(round(distance * self.calibration[0]))
            else:
                return 0
        else:
            # TODO: define conversion for other types of stages
            return 0

    def convert_to_unit(self, step_distance):
        """ Convert the steps back in to a readable unit

        Forward (pos) and backward (neg) pitch are different (from manual)
        Therefore need to calculate conversion for forward and backward motion
        """

        if self.unit == 'degrees':
            if step_distance < 0:
                # do conversion for neg direction, based on backwards calibration
                return float(round(step_distance / self.calibration[1], 1))
            elif step_distance > 0:
                # do conversion for pos direction, based on forwards calibration
                return float(round(step_distance / self.calibration[0], 1))
            else:
                # throw up an error
                raise Exception('No direction given for the conversion')
        else:
            # TODO: define conversion for other types of stages
            return 0

    def get_velocity(self, speed):
        """ Get the step amplitude value for the motor, both pos and neg direction """
        print('Motor: {0}, Forward: {1}, Backward: {2}'.format(self.label, speed[0], speed[1]))

    def get_status(self, state):
        return state
        # if state == 1:
        #     # output that it is stepping
        #     print('Motor: {0} is stepping'.format(self.label))
        #     return state
        # elif state == 2:
        #     # output that it is jogging
        #     print('Motor: {0} is jogging'.format(self.label))
        #     return state
        # elif state == 3:
        #     # output that it is moving to limit
        #     print('Motor: {0} is moving to limit'.format(self.label))
        #     return state
        # else:
        #     # device is not moving
        #     print('Motor: {0} is ready'.format(self.label))
        #     return state

    def get_steps(self, steps):
        print('Motor: {0}, Steps Taken: {1}'.format(self.label, steps))

class AgilisController(Base, MotorInterface):
    """
    This module implements comms to the Newport Agilis controller (AG-UC8)

    An example config entry would look like this;

    agilis_motor:
        module.Class: 'motor.agilis_controller.AgilisController'
        com_interface: 'COM4'
        axis_labels:
            - hwp_532
        hwp_532:
            motor_type: PR100
            channel: 1
            axis: 1
            unit: 'degrees'
            pos_pitch: 580
            neg_pitch: 506
            constraints:
                pos_min: -360
                pos_max: 720

    where the pitch is the number of steps in the direction it takes to move 1 unit

    """

    _modtype = 'AgilisController'
    _modclass = 'hardware'

    _com_interface = ConfigOption('com_interface', 'COM4', missing='warn')
    _axis_label_list = ConfigOption('axis_labels', missing='warn')

    _error_codes = {0: "No error",
                    -1: "Unknown command",
                    -2: "Axis out of range",
                    -3: "Wrong format for parameter",
                    -4: "Parameter out of range",
                    -5: "Not allowed in local mode",
                    -6: "Not allowed in current state"}

    def on_activate(self):
        """ Activate this ensuring the position is pulled from the last deactivation
        """
        self._connect_agilis(self._com_interface)

        self._axis_dict = {}

        # TODO: fix the defunct self.getConfiguration() route to implement ConfigOption
        config = self.getConfiguration()

        for axis_label in self._axis_label_list:
            self._axis_dict[axis_label] = AgilisMotor(
                config[axis_label]['motor_type'],
                config[axis_label]['channel'],
                config[axis_label]['axis'],
                axis_label,
                config[axis_label]['unit'],
                config[axis_label]['pos_pitch'],
                config[axis_label]['neg_pitch'],
                config[axis_label]['constraints'],
                self._statusVariables[axis_label]
            )

            # Ensure the velocity is as it should be
            self.set_velocity({axis_label})
            self.get_pos({axis_label})

    def on_deactivate(self):
        """ Deactivate this
        Since there is no way of maintaining knowledge of the current position the current position
        is written to the _statusVariables under the axis label. This provides some pseudo-closed-loop
        control as the controller will know where the motor finished when activated/deactivated
        """
        self._disconnect_agilis()

        # The cheat...
        for axis_label in self._axis_label_list:
            self._statusVariables[axis_label] = self._axis_dict[axis_label].get_current_position()

    def _connect_agilis(self, interface):
        """ Connect to Agilis Controller
        """
        try:
            self.rm = visa.ResourceManager()
            rate = 921600
            self.inst = self.rm.open_resource(
                interface,
                baud_rate=rate,
                data_bits=8,
                parity=visa.constants.Parity.none,
                stop_bits=visa.constants.StopBits.one,
                write_termination='\r\n',
                read_termination='\r\n',
                query_delay=0.1,
                send_end=True)
            # give controller 2 seconds maximum to reply
            self.inst.timeout = 2000
            self.inst.write('MR')

            # Add in a small delay to help the controller not timeout!
            time.sleep(0.1)
            if self.check_for_errors() != 0:
                # forcing to write remote again after timeout helps
                self.inst.write('MR')
                self.log.error('Could not set remote mode')

        except visa.VisaIOError:
            self.log.exception('Communication Failure:')
            return False
        else:
            return True

    def _disconnect_agilis(self):
        """ Close connection
        """
        #self.inst.write('ML')
        self.inst.close()
        #self.rm.close()

    def get_constraints(self):
        """ Retrieve the hardware constrains from the motor device.

        @return dict: dict with constraints for the magnet hardware. These
                      constraints will be passed via the logic to the GUI so
                      that proper display elements with boundary conditions
                      could be made.

        Provides all the constraints for each axis of a motorized stage
        (like total travel distance, velocity, ...)
        Each axis has its own dictionary, where the label is used as the
        identifier throughout the whole module. The dictionaries for each axis
        are again grouped together in a constraints dictionary in the form

            {'<label_axis0>': axis0 }

        where axis0 is again a dict with the possible values defined below. The
        possible keys in the constraint are defined here in the interface file.
        If the hardware does not support the values for the constraints, then
        insert just None. If you are not sure about the meaning, look in other
        hardware files to get an impression.

        Example of how a return dict with constraints might look like:
        ==============================================================

        constraints = {}

        axis0 = {}
        axis0['label'] = 'x'    # it is very crucial that this label coincides
                                # with the label set in the config.
        axis0['unit'] = 'm'     # the SI units, only possible m or degree
        axis0['ramp'] = ['Sinus','Linear'], # a possible list of ramps
        axis0['pos_min'] = 0,
        axis0['pos_max'] = 100,  # that is basically the traveling range
        axis0['pos_step'] = 100,
        axis0['vel_min'] = 0,
        axis0['vel_max'] = 100,
        axis0['vel_step'] = 0.01,
        axis0['acc_min'] = 0.1
        axis0['acc_max'] = 0.0
        axis0['acc_step'] = 0.0

        axis1 = {}
        axis1['label'] = 'phi'   that axis label should be obtained from config
        axis1['unit'] = 'degree'        # the SI units
        axis1['ramp'] = ['Sinus','Trapez'], # a possible list of ramps
        axis1['pos_min'] = 0,
        axis1['pos_max'] = 360,  # that is basically the traveling range
        axis1['pos_step'] = 100,
        axis1['vel_min'] = 1,
        axis1['vel_max'] = 20,
        axis1['vel_step'] = 0.1,
        axis1['acc_min'] = None
        axis1['acc_max'] = None
        axis1['acc_step'] = None

        # assign the parameter container for x to a name which will identify it
        constraints[axis0['label']] = axis0
        constraints[axis1['label']] = axis1
        """

        constraints = dict()
        for axis_label in self._axis_label_list:
            axis_constraints = dict()
            axis_constraints['label'] = axis_label
            axis_constraints['unit'] = self._axis_dict[axis_label].unit

            position_constraints = self._axis_dict[axis_label].get_constraints()

            axis_constraints['pos_min'] = position_constraints['pos_min']
            axis_constraints['pos_max'] = position_constraints['pos_max']
            axis_constraints['pos_step'] = position_constraints['pos_step']
            axis_constraints['vel_min'] = None
            axis_constraints['vel_max'] = None
            axis_constraints['vel_step'] = None
            axis_constraints['acc_min'] = None
            axis_constraints['acc_max'] = None
            axis_constraints['acc_step'] = None

            constraints[axis_label] = axis_constraints

        return constraints

    def _set_channel(self, motor):
        """ Set the channel on AG-UC8
        """
        if motor._channel > 4:
           return Exception('Channel number is not possible')
        else:
            use_channel = motor._channel
            self.inst.write('CC{0}'.format(use_channel))

            # Add in a small delay to help the controller not timeout!
            time.sleep(0.1)

    def move_rel(self,  param_dict):
        """ Moves stage in given direction (relative movement)

        @param dict param_dict: dictionary, which passes all the relevant
                                parameters, which should be changed. Usage:
                                 {'axis_label': <the-abs-pos-value>}.
                                 'axis_label' must correspond to a label given
                                 to one of the axis.

        A smart idea would be to ask the position after the movement.

        @return int: error code (0:OK, -1:error)
        """
        error_count = 0
        for axis_label in param_dict:
            # Define the motor
            motor = self._axis_dict[axis_label]

            # Do the motion
            error_count += self._move_relative(motor, param_dict[axis_label])
        return error_count == 0

    def _move(self, motor):
        # do motion
        use_axis = motor._axis
        move = motor.convert_to_step(self.target)

        self.inst.write('{0}PR{1}'.format(use_axis, move))

        # Add in a small delay to help the controller not timeout!
        time.sleep(0.1)

        rc = self.check_for_errors()
        if rc != 0:
            self.log.warn("Agilis controller error {} {}".format(rc, self.error_string(rc)))
            return 1
        else:
            return 0

    def _move_relative(self, motor, relative_distance):
        # connect to the right channel
        self._set_channel(motor)

        # Handle the target
        self.target = relative_distance

        # Reset the step counter
        self._zero(motor)

        # update the current position with the relative motion
        motor.set_move_rel(relative_distance)

        # Make sure we don't pass a zero degree movement
        if relative_distance == 0:
            return 0
        else:
            return self._move(motor)

    def move_abs(self, param_dict):
        error_count = 0
        for axis_label in param_dict:
            # Define the motor
            motor = self._axis_dict[axis_label]

            # Do the motion
            error_count += self._move_absolute(motor, param_dict[axis_label])
        return error_count == 0

    def _move_absolute(self, motor, absolute_distance):
        # connect to the right channel
        self._set_channel(motor)
        self.target = absolute_distance

        # Reset the step counter
        self._zero(motor)

        # get the current position value from the dictionary of positions
        current_pos = motor.get_current_position()

        # Work out the difference between target and current position
        self.target = absolute_distance - current_pos

        # update the current position with the difference
        motor.set_move_abs(self.target)

        return self._move(motor)

    def abort(self, param_list=None):
        """
        This is done with a nasty, but useful, hack. Everytime the motor is told to move it resets
        the step counter to zero. The abort function then reads the step counter and converts back to a unit
        based on the calibration so that the current position can be updated with how far it actually moved
        before it was told so rudely to stop.

        This is currently written with PR100 in mind and should be altered if additional stages are implemented
        """

        try:
            # check that there is a target set to move
            self.target
        except NameError:
            self.log.warning('No Target Value Found')
        else:
            # Continue as normal
            if param_list is not None:
                # Abort specific motor
                for axis_label in param_list:
                    motor = self._axis_dict[axis_label]

                    # Do the stop
                    self._stop(motor)

                    # Find out the number of steps moved after the motion
                    actual_steps = self.get_steps(motor)

                    # Find out direction of travel if pos or neg and do the convert to unit
                    actual_dist = float(round(motor.convert_to_unit(actual_steps), 1))

                    # Update the current position with the correct value
                    motor.abort(self.target, actual_dist)
                    self.log.info('Movement of {0} stopped after {1} {2}'.format(motor.label, actual_dist, motor.unit))
            else:
                # Abort all motors
                for axis_label in self._axis_dict:
                    motor = self._axis_dict[axis_label]

                    # Do the stop
                    self._stop(motor)

                    # Find out the number of steps moved after the motion
                    actual_steps = self.get_steps(motor)

                    # Find out direction of travel if pos or neg and do the convert to unit
                    actual_dist = float(round(motor.convert_to_unit(actual_steps), 1))

                    # Update the current position with the correct value
                    motor.abort(self.target, actual_dist)
                    self.log.info('Movement of {0} stopped after {1} {2}'.format(motor.label, actual_dist, motor.unit))

    def _stop(self, motor):
        """ Stops the motion on the defined axis. Sets the state to ready
        xxST where xx is the axis number on the channel set
        """
        # Connect to the right channel
        self._set_channel(motor)
        use_axis = motor._axis
        self.inst.write('{0}ST'.format(use_axis))

        # Add in a small delay to help the controller not timeout!
        time.sleep(0.1)

    def get_pos(self, param_list=None):
        if param_list is not None:
            for axis_label in param_list:
                if axis_label in self._axis_dict:
                    pos = self._axis_dict[axis_label].get_current_position()
                    #print('{0} is at {1} {2}'.format(axis_label, pos[axis_label], self._axis_dict[axis_label].unit))
                    #return pos[axis_label]
        else:
            pos = {}
            for axis_label in self._axis_dict:
                pos[axis_label] = self._axis_dict[axis_label].get_current_position()
                #print('{0} is at {1} {2}'.format(axis_label, pos[axis_label], self._axis_dict[axis_label].unit))
                #return pos[axis_label]

        return pos

    def _get_status(self, x):
        motor = self._axis_dict[x]
        # Ensure we're on the right channel
        self._set_channel(motor)

        # Query for the current state
        response = self.inst.query('{0}TS'.format(motor._axis))
        m = re.match('.*TS(\d+)',response)
        if m is None:
            self.log.warn("Unexpected response to get status {}".format(response))
            return -1
        else:
            status = int(m.group(1))
            motor.get_status(status)
            return status

    def get_status(self, param_list=None):
        """ Get the status of the position
        ASCII Command; xxTS
        where xx is the axis number in the channel

        Returns:
            0 for Ready (Not Moving)
            1 for Stepping
            2 for Jogging
            3 for Moving to Limit (not applicable for PR100 mounts)
        """
        if param_list is not None:
            return self._get_status(param_list)
        else:
            for axis_label in self._axis_dict:
                self._get_status(axis_label)

    def check_for_errors(self):
        error = self.inst.query('TE')
        m = re.match('TE(\-?\d+)', error)
        if m is None:
            self.log.error("Agilis error code not as expected! {}".format(error))
            return -99
        else:
            rc = m.group(1)
            return int(rc)

    def error_string(self, c):
        try:
            return self._error_codes[c]
        except:
            return "Unexpected error code"

    def calibrate(self, param_list=None):
        """ Calibrates the stage.

        @param dict param_list: param_list: optional, if a specific calibration
                                of an axis is desired, then the labels of the
                                needed axis should be passed in the param_list.
                                If nothing is passed, then all connected axis
                                will be calibrated.

        @return int: error code (0:OK, -1:error)

        After calibration the stage moves to home position which will be the
        zero point for the passed axis. The calibration procedure will be
        different for each stage.
        """
        return 0

    def get_velocity(self, param_list=None):
        """ Gets the current velocity for all connected axes.
            In this case, the step amplitude
        @param dict param_list: optional, if a specific velocity of an axis
                                is desired, then the labels of the needed
                                axis should be passed as the param_list.
                                If nothing is passed, then from each axis the
                                velocity is asked.

        @return dict : with the axis label as key and the velocity as item.
        """
        vel = {}

        if param_list is not None:
            motor = self._axis_dict[param_list]
            # Ensure we're on the right channel
            self._set_channel(motor)

            vel[param_list] = [int(self.inst.query('{0}SU+?'.format(motor._axis)).split('SU+')[1]),
                               int(self.inst.query('{0}SU-?'.format(motor._axis)).split('SU-')[1])]

            motor.get_velocity(vel[param_list])

        else:
            for axis_label in self._axis_dict:
                motor = self._axis_dict[axis_label]
                # Ensure we're on the right channel
                self._set_channel(motor)

                vel[axis_label] = [int(self.inst.query('{0}SU+?'.format(motor._axis)).split('SU+')[1]),
                                   int(self.inst.query('{0}SU-?'.format(motor._axis)).split('SU-')[1])]

                motor.get_velocity(vel[axis_label])

    def set_velocity(self, param_dict):
        """ Write new value for velocity.

        @param dict param_dict: dictionary, which passes all the relevant
                                parameters, which should be changed. Usage:
                                 {'axis_label': <the-velocity-value>}.
                                 'axis_label' must correspond to a label given
                                 to one of the axis.

        @return int: error code (0:OK, -1:error)
        """
        # Default option to just set the step amp to the largest value in both directions
        # RFE: probably want to set the default amp in the config? Do we want diff vals for each motor?
        default_amp = 50

        for axis_label in param_dict:
            motor = self._axis_dict[axis_label]
            use_axis = motor._axis
            self.inst.write('{0}SU{1}'.format(use_axis, default_amp))

            # Add in a small delay to help the controller not timeout!
            time.sleep(0.1)

            self.inst.write('{0}SU{1}'.format(use_axis, -default_amp))

            # Add in a small delay to help the controller not timeout!
            time.sleep(0.1)

    def set_home(self,  param_dict):
        """ Once the motor is in the right position which reads zero
        on the motor itself, we can manually adjust our zero point in Qudi

        NOTE: This will mess up the psuedo-closed-loop style approach if
        this is called when the motor doesn't physically read zero so only call
        this when this is true
        """
        for axis_label in param_dict:
            motor = self._axis_dict[axis_label]

            # Pass to the motor that the position should now be 0 degrees
            motor._current_position = 0

            self._zero(motor)

            self.log.info('Motor {0} has been reset to zero degrees'.format(motor.label))
            return self.get_pos()

    def _zero(self, motor):
        # connect to the right channel
        self._set_channel(motor)
        use_axis = motor._axis

        # Tell the controller we want this to be the zero position
        self.inst.write('{0}ZP'.format(use_axis))

        # Add in a small delay to help the controller not timeout!
        time.sleep(0.1)

    def get_steps(self, param_list=None):
        """ Returns the number of steps by the sum of forward - backward """

        steps = {}

        if param_list is not None:
            motor = self._axis_dict[param_list]
            # Ensure we're on the right channel
            self._set_channel(motor)

            steps[param_list] = int((self.inst.query('{0}TP'.format(motor._axis))).split('TP')[1])

            motor.get_steps(steps[param_list])
            #return steps[param_list]

        else:
            for axis_label in self._axis_dict:
                motor = self._axis_dict[axis_label]
                # Ensure we're on the right channel
                self._set_channel(motor)

                steps[param_list] = int((self.inst.query('{0}TP'.format(motor._axis))).split('TP')[1])

                motor.get_steps(steps[param_list])
                #return steps[param_list]

    def set_steps(self, motor, steps):
        self._set_channel(motor)
        use_axis = motor._axis

        # Tell the motor to move x amount of steps
        self.inst.write('{0}PR{1}'.format(use_axis, steps))

        # Add in a small delay to help the controller not timeout!
        time.sleep(0.1)

        # Check this is sensible and doesn't throw an error
        rc = self.check_for_errors()
        if rc != 0:
            self.log.warn("Agilis controller error {} {}".format(rc, self.error_string(rc)))
            return 1
        else:
            return 0

    # TODO: add in jogging commands
    def jogging_move(self, param_dict):
        """ Starts a jog motion at a defined speed.
        Defined steps are steps with the set step amplitude.
        Max amp steps are equivalent to step amp = 50
        ASCII Command; xxJAnn
        where xx is the axis number in the channel
        nn is the direction and speed

        Set nn to:
            -4:     negative direction 666 steps/s
            -3:     negative direction 1700 steps/s
            -2:     negative direction 100 steps/s
            -1:     negative direction 5 steps/s
             0:     No move, go to READY state
             1:     positive direction 5 steps/s
             2:     positive direction 100 steps/s
             3:     positive direction 1700 steps/s
             4:     positive direction 666 steps/s
        """

        error_count = 0
        for axis_label in param_dict:
            # Define the motor
            motor = self._axis_dict[axis_label]

            # Do the motion
            error_count += self._jog(motor, param_dict[axis_label])
        return error_count == 0


    def _jog(self, motor, speed):
        # Connect to the right motor
        self._set_channel(motor)
        use_axis = motor._axis

        # Reset the step counter
        #if speed != 0:
        self._zero(motor)

        # do jog ...
        self.inst.write('{0}JA{1}'.format(use_axis, speed))

        # Add in a small delay to help the controller not timeout!
        time.sleep(0.1)

        # Check this is sensible and doesn't throw an error
        rc = self.check_for_errors()
        if rc != 0:
            self.log.warn("Agilis controller error {} {}".format(rc, self.error_string(rc)))
            return 1
        else:
            return 0
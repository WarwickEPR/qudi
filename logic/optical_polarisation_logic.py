"""
This module manages the stages attached to the Agilis Controller

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
import numpy as np
import TimeTagger as tt
import matplotlib.pyplot as plt

from qtpy import QtCore
from core.module import Connector, ConfigOption, StatusVar
from core.util.mutex import Mutex
from logic.generic_logic import GenericLogic
from collections import OrderedDict


class OpticalPolLogic(GenericLogic):
    """
    This is the logic for making a "quick" optical polarisation measurement
    """

    _modclass = 'polarizationlogic'
    _modtype = 'logic'

    # -------------------
    # Declare connectors
    # -------------------

    motorstage = Connector(interface='MotorInterface')
    savelogic = Connector(interface='SaveLogic')
    fitlogic = Connector(interface='FitLogic')
    counter = Connector(interface='SlowCounterInterface')

    # -------------------
    # Keep track of stuff
    # -------------------
    # Motor Update
    motor_update = QtCore.Signal()
    # Data handling
    pol_data = QtCore.Signal()
    # Fitting update
    pol_fit_updated = QtCore.Signal()
    # Saving of the data
    pol_saved = QtCore.Signal()

    was_moving = False

    #sigMoveAbs = QtCore.Signal(dict)
    #sigMoveRel = QtCore.Signal(dict)
    sigAbort = QtCore.Signal()

    # Signals for making the move_abs, move_rel and abort independent:
    sigHomeStart = QtCore.Signal()
    sigHomeStop = QtCore.Signal()
    sigMovementStart = QtCore.Signal()
    sigMovementStop = QtCore.Signal()
    sigMeasurementStart = QtCore.Signal()
    sigMeasurementStop = QtCore.Signal()
    sigStopped = QtCore.Signal()
    sigNextPoint = QtCore.Signal()

    # -------------------
    # Config Options
    # -------------------
    #_angle_resolution = ConfigOption('resolution', missing='error')

    _channel_apd_0 = ConfigOption('timetagger_channel_apd_0', missing='error')
    _channel_apd_1 = ConfigOption('timetagger_channel_apd_1', None, missing='warn')

    _measurement_length = ConfigOption('measurement_length', missing='error')
    _count_frequency = ConfigOption('count_frequency', missing='error')

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)

        # start fresh
        self._excitation_angles = []
        self.pol_data = []
        self.pol_fit = []
        self.fit_min = 0.0
        self.fit_max = 0.0
        self.pol_fitted = False
        self.pol_collected = False
        self.stop_requested = False

        # locking for thread safety
        self.threadlock = Mutex()

    def on_activate(self):
        """ Connect to the controller """

        # -------------------
        # Sort out the connectors
        # -------------------
        # give a connection to the motor stage
        self._motor_stage = self.get_connector('motorstage')
        # pull out the names of the connected motors
        self._motor_list = self.get_axes()
        self._save_logic = self.get_connector('savelogic')

        # TODO: ?get motor capabilities to put into dictionary so they can be updated?

        # EXPERIMENTAL (from logic/magnet_logic.py):
        # connect now directly signals to the interface methods, so that
        # the logic object will be not blocks and can react on changes or abort
        #self.sigMoveAbs.connect(self._motor_stage.move_abs)
        #self.sigMoveRel.connect(self._motor_stage.move_rel)
        self.sigAbort.connect(self._motor_stage.abort)

        # -------------------
        # Sort out the TT stuff
        # -------------------
        # setup timetagger
        self._tagger = tt.createTimeTagger()

        # combine timetagger channels
        self._channel_combined = tt.Combiner(self._tagger, channels=[self._channel_apd_0, self._channel_apd_1])
        self._channel_apd = self._channel_combined.getChannel()

        # -------------------
        # Setup Timers
        # -------------------
        self.home_timer = QtCore.QTimer()
        self.home_timer.timeout.connect(self.check_motor_homed)
        self.movement_timer = QtCore.QTimer()
        self.movement_timer.timeout.connect(self.check_motor_stopped)
        self.measurement_timer = QtCore.QTimer()
        self.measurement_timer.timeout.connect(self.measurement_complete)

        # -------------------
        # Connect the signals
        # -------------------
        self.sigHomeStart.connect(self._start_homing_timer)
        self.sigHomeStop.connect(self._stop_homing_timer)
        self.sigMovementStart.connect(self._start_movement_timer)
        self.sigMovementStop.connect(self._stop_movement_timer)
        self.sigMeasurementStart.connect(self._start_measurement_timer)
        self.sigMeasurementStop.connect(self._stop_measurement_timer)
        self.sigNextPoint.connect(self.move_to_next_position, QtCore.Qt.QueuedConnection)

    def on_deactivate(self):
        """ Deactivate module.
        """
        self.sigHomeStart.disconnect()
        self.sigHomeStop.disconnect()
        self.sigMovementStart.disconnect()
        self.sigMovementStop.disconnect()
        self.sigMeasurementStart.disconnect()
        self.sigMeasurementStop.disconnect()
        self.sigNextPoint.disconnect()
        self.measurement_timer.stop()
        self.home_timer.stop()
        self.movement_timer.stop()

        return 0

    # function to start the measurement
    def run_pol(self, motor, start_angle, end_angle, resolution):
        # be careful that the goto_home isn't called if the start angle is not zero
        self._excitation_angles = [start_angle, end_angle]
        self._angle_resolution = resolution

        self.target_position = start_angle
        self.measurement_motor = motor

        # setup pol_data to be on the order of the measurement
        #plt.close('all')
        self._cell_id = 0
        data_points = int((end_angle-start_angle)/resolution + 1)
        self.pol_data = np.zeros((data_points, 2))

        self.goto_home(motor)

    # function to home the motor to the starting angle
    def goto_home(self, motor):
        self.log.info('Getting the motor to the start position')
        # find out where the motor currently is and move if not zero
        self.motor_position = self.get_pos([motor])

        # if not at the starting angle, go there
        self.log.info("Motor pos: {} Target: {}".format(self.motor_position, self.target_position))
        if self.motor_position != self.target_position:
            # move to zero (or home) by doing sending -self.motor_position
            if self.move_abs({motor: self.target_position}):
                self.log.info('Moving {0} to the start position'.format(motor))
                self.sigHomeStart.emit()
            else:
                self.log.warn("Failed to move to start position")
        # we're at the starting angle already
        elif self.motor_position == self.target_position:
            self.log.info('{0} is already at the starting position!'.format(motor))
            self.sigNextPoint.emit()
        # Impossible to read the position
        else:
            self.log.warning('unable to read motor position')

    def _start_homing_timer(self):
        self.home_timer.start(1000)

    def check_motor_homed(self):
        motor = self.measurement_motor
        motor_moving = self.get_status(motor)

        if motor_moving != 0:
            self.was_moving = True
        elif self.was_moving:
            self.log.info('Motor finished homing')
            self.was_moving = False
            self._stop_homing_timer()
            self.motor_position = self.get_pos([motor])
            self.sigNextPoint.emit()
        else:
            pass

    def _stop_homing_timer(self):
        self.home_timer.stop()

    def move_to_next_position(self):
        motor = self.measurement_motor
        self.log.debug("Moving to next point")
        self.log.debug("Motor pos: {} Target: {}".format(self.motor_position, self.target_position))
        if self.motor_position != self.target_position:
            if self.move_abs({motor: self.target_position}):
                self.log.info('Moving to position {0}'.format(self.target_position))
                self.sigMovementStart.emit()
            else:
                self.log.warn('Failed to move to position {0}'.format(self.target_position))
        else:
            self.log.info("Already at position {0}".format(self.target_position))
            self.start_measurement()

    def _start_movement_timer(self):
        self.movement_timer.start(1000)

    def check_motor_stopped(self):
        motor = self.measurement_motor
        motor_moving = self.get_status(motor)

        if motor_moving != 0:
            self.was_moving = True
        elif self.was_moving:
            self.log.info('Motor finished moving')
            self.was_moving = False
            self.motor_position = self.get_pos([motor])
            self.sigMovementStop.emit()
            self.start_measurement()
        else:
            pass

    def _stop_movement_timer(self):
        self.movement_timer.stop()

    def start_measurement(self):
        self.log.info('Starting measurement')
        self.setup_counter()
        self.sigMeasurementStart.emit()

    def _start_measurement_timer(self):
        self.measurement_timer.start(1000*self._measurement_length+100)

    def measurement_complete(self):
        self.sigMeasurementStop.emit()
        self.log.info('Measurement step complete')
        data = self.counter.getData()*self._count_frequency
        self.log.info('Average counts: {0}'.format(np.mean(data)))

        # feed into array so that we can save it file later?
        self.store_counts(np.mean(data))

        if self.stop_requested:
            self.log.info('Measurement stopped at your request')
            self.save_pol()
            self.pol_collected = True
            return

        if self.target_position < self._excitation_angles[1]:
            self.target_position += self._angle_resolution
            self.sigNextPoint.emit()
        else:
            self.log.info('Measurement complete')
            self.save_pol()
            self.pol_collected = True

    def _stop_measurement_timer(self):
        self.measurement_timer.stop()

    def store_counts(self, counts):
        self.pol_data[self._cell_id][0] = self.target_position
        self.pol_data[self._cell_id][1] = counts
        self._cell_id += 1

    def save_pol(self):
        # File path and name
        filepath = self._save_logic.get_path_for_module(module_name='Polarization')

        # We will fill the data OrderedDict to send to savelogic
        data = OrderedDict()

        # Lists for each column of the output file
        angle = [row[0] for row in self.pol_data]
        counts = [row[1] for row in self.pol_data]

        data['Angle'] = angle
        data['Count rate (/s)'] = counts

        # set up figure?
        plt.style.use(self._save_logic.mpl_qd_style)
        fig, ax1 = plt.subplots()
        ax1.plot(angle, counts)
        ax1.set_xlabel('Angle (deg)')
        ax1.set_ylabel('Counts (cps)')
        fig.tight_layout()

        self._save_logic.save_data(data, filepath=filepath, filelabel='Pol', fmt=['%.6f', '%.6f'], plotfig=fig)
        self.log.info('Excitation Polarisation saved to:\n{0}'.format(filepath))

        return 0

    def stop_pol(self):
        self.stop_requested = True
        self.sigAbort.emit()

    def setup_counter(self):
        self.counter = tt.Counter(
            self._tagger,
            channels=[self._channel_apd],
            binwidth=int((1 / self._count_frequency) * 1e12),
            n_values=self._measurement_length * self._count_frequency)

        self.counter.clear()
        self.counter.start()

    def get_counter_data(self):
        return self.counter.getData() * self._count_frequency

    def get_axes(self):
        return self._motor_stage._axis_label_list

    # From Magnet logic
    # TODO: Fix
    def get_hardware_constraints(self):
        """ Retrieve the hardware constraints.

        @return dict: dict with constraints for the magnet hardware. The keys
                      are the labels for the axis and the items are again dicts
                      which contain all the limiting parameters.
        """
        return self._motor_stage.get_constraints()

    def move_rel(self, param_dict):
        """ Move the specified axis in the param_dict relative with an assigned
            value.

        @param dict param_dict: dictionary, which passes all the relevant
                                parameters. E.g., for a movement of an axis
                                labeled with 'x' by 23 the dict should have the
                                form:
                                    param_dict = { 'x' : 23 }
        @return param dict: dictionary, which passes all the relevant
                                parameters. E.g., for a movement of an axis
                                labeled with 'x' by 23 the dict should have the
                                form:
                                    param_dict = { 'x' : 23 }
        """
        return self._motor_stage.move_rel(param_dict)

    def move_abs(self, param_dict):
        """ Moves stage to absolute position (absolute movement)

        @param dict param_dict: dictionary, which passes all the relevant
                                parameters, which should be changed. Usage:
                                 {'axis_label': <a-value>}.
                                 'axis_label' must correspond to a label given
                                 to one of the axis.

        @return param dict: dictionary, which passes all the relevant
                                parameters. E.g., for a movement of an axis
                                labeled with 'x' by 23 the dict should have the
                                form:
                                    param_dict = { 'x' : 23 }
        """

        return self._motor_stage.move_abs(param_dict)

    def get_pos(self, param_list=None):
        """ Gets current position of the stage.

        @param list param_list: optional, if a specific position of an axis
                                is desired, then the labels of the needed
                                axis should be passed as the param_list.
                                If nothing is passed, then from each axis the
                                position is asked.

        @return dict: with keys being the axis labels and item the current
                      position.
        """

        pos_dict = self._motor_stage.get_pos(param_list)
        return pos_dict

    def get_status(self, param_list=None):
        """ Get the status of the position

        @param list param_list: optional, if a specific status of an axis
                                is desired, then the labels of the needed
                                axis should be passed in the param_list.
                                If nothing is passed, then from each axis the
                                status is asked.

        @return dict: with the axis label as key and  a tuple of a status
                     number and a status dict as the item.
        """
        status = self._motor_stage.get_status(param_list)
        return status

    def stop_movement(self):
        """ Stops movement of the stage. """
        self._stop_measure = True
        self.sigAbort.emit()
        return self._stop_measure

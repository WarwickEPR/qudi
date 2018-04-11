"""
This module provides the logic to perform a series of XY images
as a function of z with the option of putting in a rotation
of laser polarisation and repeat the same XY before moving to
the next z location.

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

import numpy as np

from qtpy import QtCore
from core.module import Connector, ConfigOption
from core.util.mutex import Mutex
from logic.generic_logic import GenericLogic
from collections import OrderedDict


class ImageStackLogic(GenericLogic):
    """
    This is the logic for stacking XY images with optional polarisation step

    n.b.: Based on the workstack logic from the workstack branch
    """

    _modclass = 'imagestacklogic'
    _modtype = 'logic'

    # -------------------
    # Declare connectors
    # -------------------

    # Put in the motors
    motorstage = Connector(interface='MotorInterface')
    # Put in the scanner logic to perform XY scans (save map from there)
    scannerlogic = Connector(interface='ConfocalLogic')
    # put in the optimizer logic for autofocus
    optimizer1 = Connector(interface='OptimizerLogic')
    # Save logic to store the experimental params
    savelogic = Connector(interface='SaveLogic')

    # -------------------
    # Define Signals
    # -------------------
    # Motor movements
    sigMovementStart = QtCore.Signal()
    sigMovementStop = QtCore.Signal()
    # Abort motor signal
    sigAbort = QtCore.Signal()
    # Signal for continuing
    sigContinueStack = QtCore.Signal()

    # -------------------
    # Define states
    # -------------------
    # choose whether we want a polarisation step or not
    _make_pol = False
    # Bool for motion of motor
    _was_moving = False
    # Are we imaging right now?
    _imaging = False
    # Lets have an option to use the surface as a reference point
    _use_surface = False
    # We start at 1, which is an odd number
    _is_even = False
    _is_odd = True

    # -------------------
    # Set up how to handle refocus
    # -------------------
    _refocus_counter = 1
    # do a refocus every x measurements (default)
    _refocus_period = 5

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)

        # start fresh

        # locking for thread safety
        self.threadlock = Mutex()

    def on_activate(self):
        """ Connect to the controller """

        # -------------------
        # Sort out the connectors
        # -------------------
        # give a connection to the motor stage
        self._motor_stage = self.get_connector('motorstage')
        self._confocal_logic = self.get_connector('scannerlogic')
        self._save_logic = self.get_connector('savelogic')
        self._optimizer_logic = self.get_connector('optimizer1')

        # TODO: ?get motor capabilities to put into dictionary so they can be updated?
        # pull out the names of the connected motors
        self._motor_list = self.get_axes()

        # -------------------
        # Setup Timers
        # -------------------
        self.timer_value = 1000

        # timer to check when the motor is done moving
        self.movement_timer = QtCore.QTimer()
        self.movement_timer.timeout.connect(self.check_motor_stopped)

        # -------------------
        # Connect the signals
        # -------------------
        # Motion of the rotation mounts
        self.sigMovementStart.connect(self._start_movement_timer)
        self.sigMovementStop.connect(self._stop_movement_timer)

        self.sigContinueStack.connect(self.run_stack, QtCore.Qt.QueuedConnection)

        # listen for the refocus to finish
        self._optimizer_logic.sigRefocusFinished.connect(self.refocused, QtCore.Qt.QueuedConnection)

        # listen for the confocal imaging to stop
        self._confocal_logic.signal_stop_scanning.connect(self.finished_image, QtCore.Qt.QueuedConnection)
        self._confocal_logic.signal_xy_data_saved.connect(self.finished_saving, QtCore.Qt.QueuedConnection)

        # EXPERIMENTAL (from logic/magnet_logic.py):
        # connect now directly signals to the interface methods, so that
        # the logic object will be not blocks and can react on changes or abort
        self.sigAbort.connect(self._motor_stage.abort)

    def on_deactivate(self):
        """ Deactivate module.
        """
        # -------------------
        # Disconnect the signals
        # -------------------
        self.sigMovementStart.disconnect()
        self.sigMovementStop.disconnect()
        self.sigAbort.disconnect()

        self.sigContinueStack.disconnect()

        self._optimizer_logic.sigRefocusFinished.disconnect(self.refocused)
        self._confocal_logic.signal_stop_scanning.disconnect(self.finished_image)
        self._confocal_logic.signal_xy_data_saved.disconnect(self.finished_saving)

        # -------------------
        # Stop timers
        # -------------------
        self.movement_timer.stop()

        return 0

##################################### Handler Functions ########################################

    # the function to start the measurement
    def start_stack(self, pol=False, z_range=20.0, z_res=1.0, surface=150.0):
        """ Starts off the whole imaging stack process.

        Choose whether we want to rotate the HWP after an XY scan

        Set the range for Z, default at 20 um

        Set the step size for Z, default at 1 um

        Give the location of the surface of the sample;
            usually we focus a sample with z = 150 um
            this should only be used if the surface is needed
            as the reference point rather than a POI

        Based on the array and subtraction method the logic will work
        from the close to the surface and ending up deeper into the
        sample being imaged

        """
        # setup if want to do a polarisation type stack
        if pol:
            self._make_pol = True
            # hard code in the name of the measurement motor for now...
            # FIXME: Make it so we shouldn't have to do this
            self.measurement_motor = 'hwp_532'

        # Make sure _imaging is False, otherwise there's a problem
        if self._imaging:
            self.log.warning('Imaging seems to be currently in progress, can you check?')

        # Same is true for the motor moving
        if self._was_moving:
            self.log.warning('The motor is moving, wait for it to stop or reset it')

        # define how far in z we'll image and at what resolution
        self.z_range = z_range
        self.z_res = z_res
        self.z_start = self._confocal_logic._current_z # in m

        # set the start of the array to 2 to ignore imaging the surface
        self.z_array = np.linspace(2, self.z_range, int(self.z_range / self.z_res))
        self.z_length = len(self.z_array)

        # set up array to store the location and the timestamp of the map
        if pol:
            self._stack_info = np.zeros((self.z_length, 3))
            self.total_measurements = self.z_length * 2
        else:
            self._stack_info = np.zeros((self.z_length, 2))
            self.total_measurements = self.z_length

        # define where the surface of the sample is
        # could use this as the autofocus reference
        # should ensure the optimizer has a big enough
        # z range to account for a large drift in z
        self._surface = surface / 1e6 # in m
        self._use_surface = True

        # Potentially use this as a way to go between two orientations
        # if the value is odd then use orientation 1 of motor
        # if the value is even then use orientation 2 of the motor
        # would have to make sure that in the case we're not doing pol
        # that the += is 2 rather than 1
        self._scan_counter = 1
        self._is_even = False
        self._is_odd = True

        # a running ID tracker
        self._cell_id = 0

        # Ok, go!
        self.run_stack()

    def run_stack(self):
        """ This is involved with the timer so is the crux of the measurement

        Decide whether the loop sees it on an odd or even number of the
        scan counter.

        If the counter is odd, this this should mean we start the XY image
        on the value from the list of z values. It's on this case that we
        should do the autofocus routine so we keep track of z

        If the counter is even, this should mean we want to rotate the HWP
        to the other location, run the same XY map, and move the motor back
        to the first position ready to move the counter to odd.
        """
        # Decide if this is an odd or even run
        self._check_odd_even()

        if self._is_odd:
            # First pass of this loop looks at whether we should refocus or not
            check_for_refocus = int((self._refocus_counter * self._refocus_period) - 1)
            # self.log.debug('Checking for the refocus point')

            if self._cell_id == check_for_refocus:
                self._refocus_counter += 1
                # self.log.debug('Should do a focus')
                # do refocus
                if self._use_surface:
                    # send the stage to the approximate location in z for the surface
                    self._confocal_logic.set_position('tmp', z=self._surface)
                    # Do the refocus
                    self._optimizer_logic.start_refocus()
                else:
                    self.log.info('No refocus happened, currently coded only for surface references')
            # Do the measurement
            else:
                # self.log.debug('No need to focus, just go to position')
                # move the motor to the choice position
                self.move_to_vertical()
        else:
            pass

        if self._is_even:
            """ 
            The result is odd, we repeat the XY at the same z, 
            or just add one to the scan counter to make it even again
            if we're not doing a polarisation step
            """
            if self._make_pol:
                # move to the opposite polarisation
                # self.log.debug('Going to move the HWP to the opposite orientation')
                self.move_to_horizontal()
            else:
                # we're not doing polarisation, so just bump everything by 1 for the next round
                # self.log.debug('The polarisation is not set to true, so we loop back')
                self.increase_counters()
                # Go back to start of run_stack
                self.sigContinueStack.emit()

    def _take_xy(self):
        # run a check for where we are in the list of z values, if we're at the end of it we should stop
        if self._cell_id < self.z_length:
            if self._is_odd:
                this_z = self._surface - ((self.z_array[self._cell_id])/1e6)
                self._stack_info[self._cell_id][0] = this_z
                self._confocal_logic.set_position('tmp', z=this_z)
                # self.log.debug('Currently on an ODD measurement, I went to z = {0} and now will take an XY image'.format(this_z))
                self.image_XY()
            else:
                # self.log.debug('Currently on an EVEN measurement, no need to move so lets do an XY image again')
                self.image_XY()
        else:
            self.log.info('The sequence of images are now done')
            self.save_stack_info()

    def _check_odd_even(self):
        if self._scan_counter % 2 == 0:
            self._is_even = True
            self._is_odd = False
        else:
            self._is_even = False
            self._is_odd = True

    def increase_counters(self):
        if self._is_even:
            self._scan_counter += 1
            self._cell_id += 1
        else:
            self._scan_counter += 1

    def save_stack_info(self):
        # File path and name
        filepath = self._save_logic.get_path_for_module(module_name='Image Stack')

        parameters = OrderedDict()
        parameters['Starting Z location (m)'] = self.z_start
        parameters['Final Z location (m)'] = self._confocal_logic._current_z
        parameters['Total Drift (m)'] = self.z_start - self._confocal_logic._current_z

        # join up the two arrays for the final one, put z_array with _stack_info
        #all_data = np.hstack((self.z_array, self._stack_info))

        data = OrderedDict()

        # Lists for each column of the output file
        delta = np.ndarray.tolist(self.z_array)
        map_z = [row[0] for row in self._stack_info]
        # Cheat to keep precision
        map_z = [round(elem, 20) for elem in map_z]

        ts_1 = [row[1] for row in self._stack_info]

        data['Delta Value'] = delta
        data['Map taken at (m)'] = map_z
        data['Timestamp 1'] = ts_1

        if self._make_pol:
            ts_2 = [row[2] for row in self._stack_info]
            data['Timestamp 2'] = ts_2

        self._save_logic.save_data(data,
                                   filepath=filepath,
                                   parameters=parameters,
                                   filelabel='ImageStack_info',
                                   fmt='%f')

        self.log.info('Parameters of the image stack saved to:\n{0}'.format(filepath))

##################################### Scanner Functions ########################################

    def image_XY(self):
        """ Run the XY image. The parameters have to be entered onto the confocal gui... """
        self._confocal_logic.start_scanning()
        self._imaging = True

    def finished_image(self):
        # hurrah
        # lets get where we are in the measurement list compared to whats left
        self.log.info("Image Stack map {0} of {1} done".format(self._scan_counter, self.total_measurements))

        # tell the system to save what we have before we move on
        self._confocal_logic.save_xy_data(custom_fp='Image Stack')

    def finished_saving(self):
        # Give back the timestamp as string
        saved_as = int(self._confocal_logic._timestamp.strftime("%Y%m%d%H%M%S"))

        if self._is_odd:
            # update the central array with timestamp to collect up at the end
            self._stack_info[self._cell_id][1] = saved_as
        else:
            self._stack_info[self._cell_id][2] = saved_as

        # deal with the counters
        self.increase_counters()
        # claim we're not imaging any more
        self._imaging = False

        # go back to run_stack
        self.run_stack()

    # The end of the refocusing
    def refocused(self, caller, p):
        self.log.info("Finished refocusing")
        self._confocal_logic.set_position('PolTarget', *p)

        # need to return the values from the autofocus so they can be used
        if self._use_surface:
            self._surface = self._optimizer_logic.optim_pos_z

        # Pass back to the handler
        self.run_stack()

##################################### Motor Functions ########################################

    # Moving things

    def move_to_vertical(self):
        # check we're not already at zero degrees
        current_position = self.get_pos([self.measurement_motor])
        # self.log.debug('The current motor position is {0} but I need to be 0'.format(current_position))

        if current_position != 0:
            self.move_abs({self.measurement_motor: 0})
            self.sigMovementStart.emit()
        else:
            # self.log.debug('The motor didnt need to move to 0 deg so will start up the XY imaging')
            self._take_xy()

    def move_to_horizontal(self):
        current_position = self.get_pos([self.measurement_motor])
        # self.log.debug('The current motor position is {0} but I need to be 45'.format(current_position))

        if current_position != 45:
            self.move_abs({self.measurement_motor: 45})
            self.sigMovementStart.emit()
        else:
            # self.log.debug('The motor didnt need to move to 45 deg so will start up the XY imaging')
            self._take_xy()

    def move_to_position(self, angle):
        self.move_abs({self.measurement_motor: angle})
        self.sigMovementStart.emit()

    # checking things

    def _start_movement_timer(self):
        self.movement_timer.start(self.timer_value)

    def check_motor_stopped(self):
        motor = self.measurement_motor
        motor_moving = self.get_status(motor)

        if motor_moving != 0:
            self._was_moving = True

        elif self._was_moving:
            self.log.info('Motor finished moving')
            self._was_moving = False
            self.motor_position = self.get_pos([motor])

            self.sigMovementStop.emit()

            # because it's stopped, it can do the _take_xy part now
            self._take_xy()

        else:
            pass

    def _stop_movement_timer(self):
        self.movement_timer.stop()

    # hardware things

    def get_axes(self):
        return self._motor_stage._axis_label_list

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
"""
This module sets up an experiment to monitor the switching rates of a defect
based on changing the laser pump power

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
import TimeTagger as tt

from qtpy import QtCore
from core.module import Connector, ConfigOption
from core.util.mutex import Mutex
from logic.generic_logic import GenericLogic
from collections import OrderedDict


class SwitchingLogic(GenericLogic):
    """
    This is the logic for making a measurement of count rates for different laser powers
    """

    _modclass = 'switchinglogic'
    _modtype = 'logic'

    # -------------------
    # Declare connectors
    # -------------------

    laser = Connector(interface='SimpleLaserInterface')
    savelogic = Connector(interface='SaveLogic')
    counter = Connector(interface='SlowCounterInterface')

    # connector for the optimiser to run autofocus periodically
    optimizer1 = Connector(interface='OptimizerLogic')
    scannerlogic = Connector(interface='ConfocalLogic')

    # -------------------
    # Keep track of stuff
    # -------------------
    # laser Update
    laser_update = QtCore.Signal()
    # Data handling
    switching_data = QtCore.Signal()
    # Saving of the data
    switching_saved = QtCore.Signal()

    sigAbort = QtCore.Signal()
    # signal for the laser power
    sigCheckPower = QtCore.Signal()
    sigPowerDone = QtCore.Signal()
    # signal for the running measurement
    sigMeasurementStart = QtCore.Signal()
    sigMeasurementStop = QtCore.Signal()
    sigNextPoint = QtCore.Signal()

    stop_requested = False

    # -------------------
    # Config Options
    # -------------------
    _channel_apd_0 = ConfigOption('timetagger_channel_apd_0', missing='error')
    _channel_apd_1 = ConfigOption('timetagger_channel_apd_1', None, missing='warn')

    _count_frequency = ConfigOption('count_frequency', missing='error')
    _laser_powers_config = ConfigOption('laser_powers', missing='error')

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)

        # start fresh
        self._cell_id = 0

        # define number of powers to look at
        self._num_of_powers = len(self._laser_powers_config)

        self._refocus_counter = 1
        # do a refocus every x measurements (default)
        self.refocus_period = 2

        # locking for thread safety
        self.threadlock = Mutex()

    def on_activate(self):
        """ Connect to the controller """

        # -------------------
        # Sort out the connectors
        # -------------------
        # give a connection to the motor stage
        self._laser = self.get_connector('laser')
        self._save_logic = self.get_connector('savelogic')
        self._optimizer_logic = self.get_connector('optimizer1')
        self._confocal_logic = self.get_connector('scannerlogic')

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
        self.check_timer = QtCore.QTimer()
        self.check_timer.timeout.connect(self.check_laser_power)
        self.timer_value = 200

        self.measurement_timer = QtCore.QTimer()
        self.measurement_timer.timeout.connect(self.power_complete)

        # -------------------
        # Connect the signals
        # -------------------
        self.sigCheckPower.connect(self._start_power_timer)
        self.sigPowerDone.connect(self._stop_power_timer)

        self.sigMeasurementStart.connect(self._start_measurement_timer)
        self.sigMeasurementStop.connect(self._stop_measurement_timer)

        self.sigNextPoint.connect(self.do_switching, QtCore.Qt.QueuedConnection)
        self.sigAbort.connect(self.stop_switching, QtCore.Qt.QueuedConnection)

        # listen for the refocus to finish
        self._optimizer_logic.sigRefocusFinished.connect(self.refocused, QtCore.Qt.QueuedConnection)

        # For silencing the logic when a refocus is called
        self._silence = True


    def on_deactivate(self):
        """ Deactivate module.
        """
        # -------------------
        # Disconnect the signals
        # -------------------
        self.sigCheckPower.disconnect()
        self.sigPowerDone.disconnect()

        self.sigMeasurementStart.disconnect()
        self.sigMeasurementStop.disconnect()

        self.sigNextPoint.disconnect()

        self._optimizer_logic.sigRefocusFinished.disconnect(self.refocused)

        self.sigAbort.disconnect()

        # -------------------
        # Stop timers
        # -------------------
        self.check_timer.stop()
        self.measurement_timer.stop()

        return 0

    def refocused(self, caller, p):
        self.log.info("Finished refocusing")
        self._confocal_logic.set_position('PolTarget', *p)
        if self._silence:
            pass
        else:
            # continue the measurement
            self.do_switching()

    def start_switching(self, refocus=False, timer=120):
        # start fresh
        self._cell_id = 0
        self._silence = False

        # pull in the config values on each new run
        self._laser_powers = self._laser_powers_config

        # redefine laser powers from mW to W
        self._laser_powers = [i / 1000 for i in self._laser_powers]

        # reset the abort
        self.stop_requested = False

        # -------------------
        # Set up how to handle refocus
        # -------------------
        # TODO: define this not in the function?
        self._refocus_counter = 1
        # do a refocus every x measurements (default)
        self._refocus_period = 2

        self.refocus = refocus

        self.QueueRefocus = False

        # Save the laser power as the experiment started to return at the end
        self.store_laser_power = self._laser.get_power()

        # Include the opportunity to modify the length of the measurement per point
        self._measurement_length = timer

        # set up array for raw data to store all counts
        self.switching_data = np.zeros((len(self._laser_powers), (self._measurement_length * self._count_frequency)))

        # Start the measurement where the target is the first value in laser powers
        self.target_power = self._laser_powers[0]

        # say that we'll start
        self.do_switching()

    def do_switching(self):
        if self.refocus:
            check_for_refocus = int((self._refocus_counter * self.refocus_period) - 1)
            if self._cell_id == check_for_refocus:
                self._refocus_counter += 1

                # send the laser back to a safe power
                self._laser.set_power(self.store_laser_power)

                # should move the call to refocus to when the laser is at the set power
                self.QueueRefocus = True

                self.log.info('Going to do a refocus at {0} mW'.format(self.store_laser_power * 1000))
                self.sigCheckPower.emit()
            else:
                # set up the array for the next set of checking powers
                self.laser_settle = []

                # Send the laser to the power needed
                self._laser.set_power(self.target_power)
                self.log.info('Sending laser to {0} mW'.format(self.target_power * 1000))

                # Start up the timer
                self.sigCheckPower.emit()

                # Run the loop for checking we're there
                self.check_laser_power()
        #TODO: tidy this up
        # this is a duplication of the else in the refocus clause
        else:
            # set up the array for the next set of checking powers
            self.laser_settle = []

            # Send the laser to the power needed
            self._laser.set_power(self.target_power)
            self.log.info('Sending laser to {0} mW'.format(self.target_power*1000))

            # Start up the timer
            self.sigCheckPower.emit()

            # Run the loop for checking we're there
            self.check_laser_power()

    def _start_power_timer(self):
        self.check_timer.start(self.timer_value)

    def check_laser_power(self):
        # check that the laser is at the power it should be before recording
        current_power = self._laser.get_power()

        # add to an array the last value read
        self.laser_settle.append(current_power)

        # Pull out the last five values to check they're all the same (ie. stopped)
        last_five = self.laser_settle[-5:]

        # returns True when all equal
        check_last_five = all(x==last_five[0] for x in last_five)

        if check_last_five:
            # interrupt based on whether we're going to refocus
            if self.QueueRefocus:
                if current_power == self.store_laser_power:
                    # Stop checking the power
                    self.sigPowerDone.emit()
                    self.QueueRefocus = False
                    self._optimizer_logic.start_refocus()
            else:
                if current_power == self.target_power:
                    self.log.info('Reached the target power: {0} mW'.format(self.target_power*1000))
                    # Stop checking the power
                    self.sigPowerDone.emit()
                    # Start the recording of counts
                    self.record_time()

    def _stop_power_timer(self):
        self.check_timer.stop()

    def record_time(self):
        # This is where the recording for measurement length happens
        self.setup_counter()
        self.sigMeasurementStart.emit()

    def _start_measurement_timer(self):
        self.measurement_timer.start(1000*self._measurement_length+100)

    def power_complete(self):
        # move on to the next power unless we're at the end
        # kill the measurement timer
        self.sigMeasurementStop.emit()

        # put the data in the array
        self.store_counts(self.get_counter_data())

        # reset the counter
        self.counter.clear()

        # check where we're at with the list of powers
        if self._cell_id == (self._num_of_powers - 1):
            # we're at the end, so stop and save
            self.stop_switching()
        else:
            # increase our count by one for the next measurement
            self._cell_id += 1

            # set the next target power from the list
            self.target_power = self._laser_powers[self._cell_id]

            #continue the loop
            self.sigNextPoint.emit()

    def _stop_measurement_timer(self):
        self.measurement_timer.stop()

    def stop_switching(self):

        if self.stop_requested:
            self.log.warning('Someone stopped the measurement')
            self.counter.stop()
            self.counter.clear()
            self.save_switching()

        self.log.info('Measurement complete')
        self.log.info('Returning back to original power: {0} mW'.format(self.store_laser_power * 1000))
        self.store_last_power = self.target_power
        self._laser.set_power(self.store_laser_power)

        # stop and clear the counter ready for next time
        self.counter.stop()
        self.counter.clear()

        self.save_switching()
        self._silence = True

    def store_counts(self, counts):
        self.switching_data[self._cell_id][:] = counts

    def save_switching(self):
        # File path and name
        filepath = self._save_logic.get_path_for_module(module_name='Switching Rates')

        parameters = OrderedDict()
        parameters['Laser Powers Defined (W)'] = self._laser_powers
        parameters['Last Measured Power (W)'] = self.store_last_power

        rawdata = OrderedDict()
        rawdata['Raw Counts (/s)'] = self.switching_data
        self._save_logic.save_data(rawdata,
                                   filepath=filepath,
                                   parameters=parameters,
                                   filelabel='Switching_rates',
                                   fmt='%f')
        self.log.info('Switching rate data saved to:\n{0}'.format(filepath))
        return 0

    def abort(self):
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
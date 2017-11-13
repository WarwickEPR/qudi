# -*- coding: utf-8 -*-
"""
A hardware module for communicating with the fast counter FPGA.

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

from interface.fast_counter_interface import FastCounterInterface
import numpy as np
import TimeTagger as tt
from enum import Enum
from core.module import Base, ConfigOption
from interface.slow_counter_interface import SlowCounterInterface
from interface.slow_counter_interface import SlowCounterConstraints
from interface.slow_counter_interface import CountingMode
import time


class MeasurementState(Enum):
    unconfigured = 0
    idle = 1
    running = 2
    paused = 3
    error = -1


class TimeTagger(Base, FastCounterInterface, SlowCounterInterface):
    _modclass = 'TimeTagger'
    _modtype = 'hardware'

    # Also do activation for fast counter
    _number_of_gates = int(100)
    _bin_width = 1
    _record_length = int(4000)

    _channels = ConfigOption('channels', missing='error')
    _combine = ConfigOption('combine', {})
    _fast_click = ConfigOption('fast_click', 'apd0', missing='warn')
    _fast_detect = ConfigOption('fast_detect', 'pulse', missing='warn')
    _slow_click = ConfigOption('slow_click', missing='error')
    _slow_clock = ConfigOption('slow_clock', 50, missing='warn')

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)

        self.channels = {}
        self.combined = {}
        self.current_measurement = None
        self.paused_measurement = None
        self.measurement_status = MeasurementState.unconfigured
        self.pulsed = None
        self.gated_counter = {}
        self.fast_click = ''
        self.fast_detect = ''
        self.slow_click = []
        self.slow_clock = 50

    def on_activate(self):
        """ Connect and configure the access to the FPGA.
        """
        self._tt = tt.createTimeTagger()
        self._tt.reset()
        config = self.getConfiguration()

        # build a register of channels
        if 'channels' in config:
            for name, c in config['channels'].items():
                self.channels[name] = c
        if 'combine' in config:
            for name, channels in config['combine'].items():
                self.combined[name] = tt.Combiner(self._tt, channels=channels)
                self.channels[name] = self.combined[name].getChannel()

        self.fast_click = config['fast_click']
        self.fast_detect = config['fast_detect']

        self.slow_click = config['slow_click']
        self.slow_clock = config['slow_clock']

        self.current_measurement = None
        self.measurement_status = MeasurementState.unconfigured

        self.log.info('TimeTagger (fast counter) configured to use  channel {0} {1}'
                      .format(self.fast_click, self.channel(self.fast_click)))

    def on_deactivate(self):
        """ Deactivate the FPGA.
        """
        if self.pulsed is not None:
            if self.getState() == 'locked':
                self.pulsed.stop()
            self.pulsed.clear()
            self.pulsed = None

    def channel(self, name):
        if name in self.channels:
            return self.channels[name]
        else:
            self.log.error("Requested channel not configured {0}".format(name))
            return tt.CHANNEL_INVALID


# Would be nice to have separate implementations for each interface
# but they share the same underlying hardware and state machine to lock
# Conceptually easiest if not most elegant way is to just implement all interfaces in
# one module. Helps to know you can outline mode the methods in PyCharm
# with Ctrl-Shift-<numpad -> and open one layer with Ctrl-Shift-<numpad *> <numpad 1>

# Exclusive use isn't required or enforced by the hardware, but in most cases
# you don't want to continue a measurement whilst other experiments are changing things

# FastCounterInterface Implementation methods (pulsed)



    # Implementation of FastCounterInterface

    def get_fast_counter_constraints(self):
        """ Retrieve the hardware constrains from the Fast counting device.

        @return dict: dict with keys being the constraint names as string and
                      items are the definition for the constaints.

         The keys of the returned dictionary are the str name for the constraints
        (which are set in this method).

                    NO OTHER KEYS SHOULD BE INVENTED!

        If you are not sure about the meaning, look in other hardware files to
        get an impression. If still additional constraints are needed, then they
        have to be added to all files containing this interface.

        The items of the keys are again dictionaries which have the generic
        dictionary form:
            {'min': <value>,
             'max': <value>,
             'step': <value>,
             'unit': '<value>'}

        Only the key 'hardware_binwidth_list' differs, since they
        contain the list of possible binwidths.

        If the constraints cannot be set in the fast counting hardware then
        write just zero to each key of the generic dicts.
        Note that there is a difference between float input (0.0) and
        integer input (0), because some logic modules might rely on that
        distinction.

        ALL THE PRESENT KEYS OF THE CONSTRAINTS DICT MUST BE ASSIGNED!
        """

        constraints = dict()

        # the unit of those entries are seconds per bin. In order to get the
        # current binwidth in seconds use the get_binwidth method.
        constraints['hardware_binwidth_list'] = [1e-9]

        # TODO: think maybe about a software_binwidth_list, which will
        #      postprocess the obtained counts. These bins must be integer
        #      multiples of the current hardware_binwidth

        return constraints

    def configure(self, bin_width_s, record_length_s, number_of_gates=0):
        return self.configure_pulsed(bin_width_s, record_length_s, number_of_gates)

    def start_measure(self):
        """ Start the fast counter. """
        return self.start_measure_pulsed()

    def stop_measure(self):
        return self.stop_measure_pulsed()

    def pause_measure(self):
        return self.pause_measure_pulsed()

    def continue_measure(self):
        return self.continue_measure_pulsed()

    def is_gated(self):
        """ Check the gated counting possibility.

        Boolean return value indicates if the fast counter is a gated counter
        (TRUE) or not (FALSE).
        """
        return True

    def get_binwidth(self):
        """ Returns the width of a single timebin in the timetrace in seconds. """
        width_in_seconds = self._bin_width * 1e-9
        return width_in_seconds

    def get_data_trace(self):
        """ Polls the current timetrace data from the fast counter.

        @return numpy.array: 2 dimensional array of dtype = int64. This counter
                             is gated the the return array has the following
                             shape:
                                returnarray[gate_index, timebin_index]

        The binning, specified by calling configure() in forehand, must be taken
        care of in this hardware class. A possible overflow of the histogram
        bins must be caught here and taken care of.
        """
        return np.array(self.pulsed.getData(), dtype='int64')

    # shared with TimeTagger as a whole
    def get_status(self):
        """ Receives the current status of the Fast Counter and outputs it as
            return value.

        0 = unconfigured
        1 = idle
        2 = running
        3 = paused
        -1 = error state
        """
        return self.measurement_status.value



    # Implementations for gated counter measurements

    def configure_gated_counter(self, name, n, click_channel, start_channel, stop_channel=None):

        if stop_channel is None:
            stop_channel = start_channel
        if name in self.gated_counter:
            self.gated_counter[name].stop()
        counter = tt.CountBetweenMarkers(self._tt,
                                         self.channel(click_channel),
                                         self.channel(start_channel),
                                         self.channel(stop_channel),
                                         n)
        self.gated_counter[name] = counter

    def start_gated_counter(self, name):
        """ Start the gated counter. """

        if name in self.gated_counter:
            counter = self.gated_counter[name]
            self.lock()
            counter.clear()
            self.current_measurement = 'gated counter ' + name
            self.measurement_status = MeasurementState.running
        else:
            self.log.error("Tried to start an unconfigured gated counter " + name)

        return 0

    def stop_gated_counter(self, name):
        """ Stop the gated counter. """
        if name in self.gated_counter:
            counter = self.gated_counter[name]
            if self.getState() == 'locked' and self.current_measurement == 'gated counter ' + name:
                self.unlock()
                self.measurement_status = MeasurementState.idle
                self.current_measurement = None
        else:
            self.log.error("Tried to stop an unconfigured gated counter " + name)

        return 0

    def pause_gated_counter(self, name):
        """ Pauses the current gated_counter measurement, if allowed.

        Must be in the run state to pause.
        """
        # TODO enforce not pauseable for refocusing

        if name in self.gated_counter \
           and self.getState() == 'locked' \
           and self.current_measurement == 'gated counter ' + name:
            self.gated_counter[name].stop()
            self.measurement_status = MeasurementState.paused
            self.paused_measurement = self.current_measurement
            self.current_measurement = None
        return 0

    def continue_gated_counter(self, name):
        """ Continues the current measurement.

        If in pause state, then gated counter will be continued.
        """
        if name in self.gated_counter \
           and self.getState() == 'locked' \
           and self.paused_measurement == 'gated counter ' + name:
            self.gated_counter[name].start()
            self.measurement_status = MeasurementState.running
            self.current_measurement = self.paused_measurement
            self.paused_measurement = None
        return 0

    def get_rates_gated_counter(self, name):
        if name in self.gated_counter:
            ctr = self.gated_counter[name]
            count = np.array(ctr.getData(), dtype='int64')
            times = np.array(ctr.getIndex(), dtype='int64')
            duration = times[1:] - times[0:-1]
            ready = duration > 0
            count = np.resize(count, len(duration))  # drop the last element
            return np.floor_divide(count[ready]*int(1e12), duration[ready])
        else:
            return np.array([], dtype='int64')

    def reset_gated_counter(self, name):
        if name in self.gated_counter:
            self.gated_counter[name].clear()
        return 0

    # Implementations for pulsed measurement
    # Configures/reconfigures fast TimeDifference counter for "pulsed"

    def configure_pulsed(self, bin_width_s, record_length_s, number_of_gates=0):

        """ Configuration of the fast counter.

        @param float bin_width_s: Length of a single time bin in the time trace
                                  histogram in seconds.
        @param float record_length_s: Total length of the timetrace/each single
                                      gate in seconds.
        @param int number_of_gates: optional, number of gates in the pulse
                                    sequence. Ignore for not gated counter.

        @return tuple(binwidth_s, gate_length_s, number_of_gates):
                    binwidth_s: float the actual set binwidth in seconds
                    gate_length_s: the actual set gate length in seconds
                    number_of_gates: the number of gated, which are accepted
        """
        self._number_of_gates = number_of_gates
        self._bin_width = bin_width_s * 1e9
        self._record_length = 1 + int(record_length_s / bin_width_s)
        self.measurement_status = MeasurementState.idle

        self.pulsed = tt.TimeDifferences(
            tagger=self._tt,
            click_channel=self.channel(self.fast_click),
            start_channel=self.channel(self.fast_detect),
            next_channel=self.channel(self.fast_detect),
            sync_channel=tt.CHANNEL_UNUSED,
            binwidth=int(np.round(self._bin_width * 1000)),
            n_bins=int(self._record_length),
            n_histograms=number_of_gates)
        self.pulsed.stop()

        return (bin_width_s, record_length_s, number_of_gates)

    def start_measure_pulsed(self):
        """ Start the fast counter. """
        self.lock()
        self.pulsed.clear()
        self.pulsed.start()
        self.current_measurement = 'pulsed'
        self.measurement_status = MeasurementState.running
        return 0

    def stop_measure_pulsed(self):
        """ Stop the fast counter. """
        if self.getState() == 'locked' and self.current_measurement == 'pulsed':
            self.pulsed.stop()
            self.unlock()
            self.measurement_status = MeasurementState.idle
            self.current_measurement = None
        return 0

    def pause_measure_pulsed(self):
        """ Pauses the current pulsed measurement.

        Fast counter must be initially in the run state to make it pause.
        """
        if self.getState() == 'locked' and self.current_measurement == 'pulsed':
            self.pulsed.stop()
            self.measurement_status = MeasurementState.paused
        return 0

    def continue_measure_pulsed(self):
        """ Continues the current measurement.

        If fast counter is in pause state, then fast counter will be continued.
        """
        if self.getState() == 'locked' and self.current_measurement == 'pulsed':
            self.pulsed.start()
            self.measurement_status = MeasurementState.running
        return 0

    # SlowCounterInterface

    def set_up_clock(self, clock_frequency=None, clock_channel=None):
        """ Configures the hardware clock of the TimeTagger for timing

        @param float clock_frequency: if defined, this sets the frequency of
                                      the clock
        @param string clock_channel: if defined, this is the physical channel
                                     of the clock

        @return int: error code (0:OK, -1:error)
        """

        self.slow_clock = clock_frequency
        return 0

    def set_up_counter(self,
                       counter_channels=None,
                       sources=None,
                       clock_channel=None,
                       counter_buffer=None):
        """ Configures the actual counter with a given clock.

        @param str counter_channel: optional, physical channel of the counter
        @param str photon_source: optional, physical channel where the photons
                                  are to count from
        @param str counter_channel2: optional, physical channel of the counter 2
        @param str photon_source2: optional, second physical channel where the
                                   photons are to count from
        @param str clock_channel: optional, specifies the clock channel for the
                                  counter
        @param int counter_buffer: optional, a buffer of specified integer
                                   length, where in each bin the count numbers
                                   are saved.

        @return int: error code (0:OK, -1:error)
        """

        self.counter = tt.Counter(self._tt,
                                  channels=list(map(lambda x: self.channel(x), self.slow_click)),
                                  binwidth=int((1/self._slow_clock) * 1e12),
                                  n_values=1)

        self.log.info('set up counter at {0} Hz'.format(self._slow_clock))
        return 0

    def get_counter_channels(self):
        return list(map(lambda x: self.channel(x), self.slow_click))

    def get_slow_counter_constraints(self):
        """ Get hardware limits the device

        @return SlowCounterConstraints: constraints class for slow counter

        FIXME: ask hardware for limits when module is loaded
        """
        constraints = SlowCounterConstraints()
        constraints.max_detectors = 2
        constraints.min_count_frequency = 1e-3
        constraints.max_count_frequency = 10e9
        constraints.counting_mode = [CountingMode.CONTINUOUS]
        return constraints

    def get_counter(self, samples=None):
        """ Returns the current counts per second of the counter.

        @param int samples: if defined, number of samples to read in one go

        @return numpy.array(uint32): the photon counts per second
        """

        time.sleep(2 / self._slow_clock)
        return np.array(list(map(lambda x: x * self._slow_clock, self.counter.getData())))

    def close_counter(self):
        """ Closes the counter and cleans up afterwards.

        @return int: error code (0:OK, -1:error)
        """
        return 0

    def close_clock(self):
        """ Closes the clock and cleans up afterwards.

        @return int: error code (0:OK, -1:error)
        """
        return 0

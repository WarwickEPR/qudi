# -*- coding: utf-8 -*-

"""
This file contains the ability to use the NI X-series cards as an analogue-based "fast counter"

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
import PyDAQmx as daq
from core.module import Base, ConfigOption
from interface.fast_counter_interface import FastCounterInterface

class NationalInstrumentsXSeriesFastCounter(Base, FastCounterInterface):
    _modtype = 'NICardFastCounter'
    _modclass = 'hardware'


    # fast counter
    _clock_channel = ConfigOption('clock_channel', missing='error')
    _sample_frequency = ConfigOption('sample_frequency', 2e6, missing='warn')
    _input_channel = ConfigOption('input_channel', missing='error')
    _trigger_channel = ConfigOption('trigger_channel', missing='warn')
    _trigger_edge = ConfigOption('trigger_edge', missing='error')
    _minimum_voltage = ConfigOption('minimum_voltage', -5, missing='warn')
    _maximum_voltage = ConfigOption('maximum_voltage', 5, missing='warn')
    _buffer_length = ConfigOption('buffer_length', 5, missing='warn')

    def on_activate(self):
        """ Starts up the NI Card at activation.
        """
        # the tasks used on that hardware device:
        self._counter_analog_daq_task = None
        self._scanner_analog_daq_task = None
        self._fast_counter_status = 1

        if 'ctr' in self._clock_channel.lower():
            self.log.info('Using internal clock for analog sampling of NI fast counter')
            self._using_external_clock = False
        else:
            self.log.info('Using external clock for analog sampling of NI fast counter')
            self._using_external_clock = True

    def on_deactivate(self):
        """ Shut down the NI card.
        """
        if  self._counter_analog_daq_task is not None:
            daq.DAQmxStopTask(self._counter_analog_daq_task)
            daq.DAQmxClearTask(self._counter_analog_daq_task)

        if self._scanner_analog_daq_task is not None:
            daq.DAQmxStopTask(self._scanner_analog_daq_task)
            daq.DAQmxClearTask(self._scanner_analog_daq_task)

    # ================== FastCounterInterface Commands ====================
    def get_constraints(self):
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

        # Example for configuration with default values:

        constraints = dict()

        # the unit of those entries are seconds per bin. In order to get the
        # current binwidth in seonds use the get_binwidth method.
        constraints['hardware_binwidth_list'] = []

        """
        constraints = dict()
        constraints['hardware_binwidth_list'] = [1 / self._sample_frequency]
        return constraints


    def configure(self, bin_width_s, record_length_s, number_of_gates=0):
        """ Configuration of the fast counter.

        @param float bin_width_s: Length of a single time bin in the time
                                  trace histogram in seconds.
        @param float record_length_s: Total length of the timetrace/each
                                      single gate in seconds.
        @param int number_of_gates: optional, number of gates in the pulse
                                    sequence. Ignore for not gated counter.

        @return tuple(binwidth_s, record_length_s, number_of_gates):
                    binwidth_s: float the actual set binwidth in seconds
                    gate_length_s: the actual record length in seconds
                    number_of_gates: the number of gated, which are accepted, None if not-gated
        """

        if self._fast_counter_status < 2:
            binwidth = 1 / self._sample_frequency
            number_of_bins = int(np.rint(record_length_s / binwidth)) + 10
            timetrace_length = number_of_bins * binwidth

            self._binwidth = binwidth
            self._number_of_bins = number_of_bins
            self._timetrace_length = timetrace_length
            self._fast_counter_status = 1
            self._number_of_gates = number_of_gates

        self.log.warn('Tracelength: {0}, binwidth: {1}, gates: {2}, bins: {3}'.format(self._timetrace_length, self._binwidth, self._number_of_gates, self._number_of_bins))

        return self._binwidth, self._timetrace_length, self._number_of_gates


    def get_status(self):
        """ Receives the current status of the Fast Counter and outputs it as
            return value.

        0 = unconfigured
        1 = idle
        2 = running
        3 = paused
       -1 = error state
        """
        return self._fast_counter_status


    def start_measure(self):
        """ Start the fast counter. """
        if self._scanner_analog_daq_task is not None:
            self.log.error('Another measurement is already running, stop this one first.')
            return -1

        physicalChannel = self._input_channel
        minV = self._minimum_voltage
        maxV = self._maximum_voltage
        samples = self._number_of_bins

        if not self._using_external_clock:
            counterChannel = self._clock_channel + 'InternalOutput'
        else:
            counterChannel = self._clock_channel

        analogTask = daq.TaskHandle()

        daq.DAQmxCreateTask("analogFastInTask", daq.byref(analogTask))

        # Setup a voltage channel to sample the analog input
        daq.DAQmxCreateAIVoltageChan(analogTask,
                                     physicalChannel,
                                     "aiChannel",
                                     daq.DAQmx_Val_RSE,
                                     minV,
                                     maxV,
                                     daq.DAQmx_Val_Volts,
                                     None)

        # Set the source of the task timing as an internal clock at the desired rate
        daq.DAQmxCfgSampClkTiming(analogTask,
                                  counterChannel,
                                  self._sample_frequency,
                                  daq.DAQmx_Val_Rising,
                                  daq.DAQmx_Val_ContSamps,
                                  samples)

        # Allocate a large enough internal buffer
        daq.DAQmxCfgInputBuffer(analogTask,
                                int(np.rint(self._buffer_length / self._binwidth)))

        # If using an internal clock rather than an external clock, we need to generate a sample frequency using one of
        # the internal counters.
        if not self._using_external_clock:
            triggerSource = self._trigger_channel
            counterTask = daq.TaskHandle()
            daq.DAQmxCreateTask("counterOutTask", daq.byref(counterTask))

            # Generate pulses on the clock channel at the correct frequency
            daq.DAQmxCreateCOPulseChanFreq(counterTask,
                                           self._clock_channel,
                                           "coChannel",
                                           daq.DAQmx_Val_Hz,
                                           daq.DAQmx_Val_Low,
                                           0,
                                           self._sample_frequency,
                                           0.5)

            # Use implicit timing to record only a finite number of analog samples
            daq.DAQmxCfgImplicitTiming(counterTask,
                                       daq.DAQmx_Val_FiniteSamps,
                                       samples)

            # Setup the trigger edge
            if self._trigger_edge == 'rising':
                edge = daq.DAQmx_Val_Rising
            else:
                edge = daq.DAQmx_Val_Falling
            daq.DAQmxCfgDigEdgeStartTrig(counterTask, triggerSource, edge)

            # Ensure trigger re-arms after each shot
            daq.DAQmxSetStartTrigRetriggerable(counterTask, True)

            self._counter_analog_daq_task = counterTask
        self._scanner_analog_daq_task = analogTask

        # easier to deal with the buffer as if it's a single linear array and recast it to the correct shape later
        self._fast_counter_data = np.zeros((self._number_of_gates * self._number_of_bins), dtype=np.uint64)
        self._circular_sample_offset = 0
        self._number_of_shots = 0

        daq.DAQmxStartTask(self._scanner_analog_daq_task)

        if self._counter_analog_daq_task is not None:
            daq.DAQmxStartTask(self._counter_analog_daq_task)

    def stop_measure(self):
        """ Stop the fast counter. """
        analogTask = self._scanner_analog_daq_task
        counterTask = self._counter_analog_daq_task

        if analogTask is not None:
            daq.DAQmxStopTask(analogTask)
            daq.DAQmxClearTask(analogTask)

        if counterTask is not None:
            daq.DAQmxStopTask(counterTask)
            daq.DAQmxClearTask(counterTask)

        self._counter_analog_daq_task = None
        self._scanner_analog_daq_task = None

        self._fast_counter_status = 1
        return self._fast_counter_status


    def pause_measure(self):
        """ Pauses the current measurement.

        Fast counter must be initially in the run state to make it pause.
        """
        analogTask = self._scanner_analog_daq_task
        counterTask = self._counter_analog_daq_task

        daq.DAQmxStopTask(analogTask)
        if counterTask is not None:
            daq.DAQmxStopTask(counterTask)

        self._fast_counter_status = 3
        return self._fast_counter_status


    def continue_measure(self):
        """ Continues the current measurement.

        If fast counter is in pause state, then fast counter will be continued.
        """
        if self._fast_counter_status != 3:
            self.log.error('Cannot continue fast counter measurement as the counter isn\'t paused')
            return self._fast_counter_status

        daq.DAQmxStartTask(self._scanner_analog_daq_task)
        if self._counter_analog_daq_task is not None:
            daq.DAQmxStartTask(self._counter_analog_daq_task)

        self._fast_counter_status = 1
        return self._fast_counter_status


    def is_gated(self):
        """ Check the gated counting possibility.

        @return bool: Boolean value indicates if the fast counter is a gated
                      counter (TRUE) or not (FALSE).
        """
        return True


    def get_binwidth(self):
        """ Returns the width of a single timebin in the timetrace in seconds.

        @return float: current length of a single bin in seconds (seconds/bin)
        """
        return 1 / self._sample_frequency


    def get_data_trace(self):
        """ Polls the current timetrace data from the fast counter.

        Return value is a numpy array (dtype = int64).
        The binning, specified by calling configure() in forehand, must be
        taken care of in this hardware class. A possible overflow of the
        histogram bins must be caught here and taken care of.
        If the counter is NOT GATED it will return a 1D-numpy-array with
            returnarray[timebin_index]
        If the counter is GATED it will return a 2D-numpy-array with
            returnarray[gate_index, timebin_index]
        """
        analogTask = self._scanner_analog_daq_task
        bins = self._number_of_bins
        gates = self._number_of_gates
        samples = gates * bins
        buffer_size = int(np.rint(self._buffer_length / self._binwidth))
        data = np.zeros((buffer_size,), dtype=np.uint16)

        numSamplesRead = daq.c_int32()

        daq.DAQmxReadBinaryU16(analogTask,
                               -1,      # read all available samples
                               0.2,     # read timeout
                               daq.DAQmx_Val_GroupByScanNumber,
                               data,
                               buffer_size,
                               daq.byref(numSamplesRead),
                               None)

        offset = self._circular_sample_offset

        if offset != 0:
            self._fast_counter_data[-offset:] += data[0:offset]

        self.log.warn('Bins: {0}, Gates: {1}. Shape of back buffer: {2}. Num samples read: {3}. Samples: {4}'.format(samples, gates, self._fast_counter_data.shape, numSamplesRead.value, samples))
        self.log.warn('First index: {0}, Second index: {1}, offset: {2}'.format(offset+1*samples, offset+(1+1)*samples,offset))
        complete_arrays = int(np.floor((numSamplesRead.value - offset)/samples))
        self._number_of_shots += complete_arrays + (1 if offset != 0 else 0)

        for k in range(0,complete_arrays):
            self._fast_counter_data[:] += data[offset+(k*samples):offset+((k+1)*samples)]

        offset = numSamplesRead.value - complete_arrays * samples - offset

        if offset != 0:
            self._fast_counter_data[:offset] += data[-offset:]

        self._circular_sample_offset = samples - offset
        return self._fast_counter_data.reshape(self._number_of_gates,self._number_of_bins) / self._number_of_shots

    # ================== End FastCounterInterface Commands ====================

# -*- coding: utf-8 -*-
"""
Use Swabian Instruments PulseStreamer8/2 as a pulse generator.

Qudi is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
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
import math
import re
import time
from collections import OrderedDict
import itertools
from more_itertools import pairwise

from core.configoption import ConfigOption
from core.connector import Connector
from core.module import Base
from interface.pulser_interface import PulserInterface, PulserConstraints
import pulsestreamer as ps

from logic.pulsed.sequence_generator_logic import SequenceGeneratorLogic


class PulseStreamer(Base, PulserInterface):

    """ Methods to control PulseStreamer.

    Example config for copy-paste:

    pulse_streamer:
        module.Class: 'swabian_instruments.pulse_streamer.PulseStreamer'
        connect:
            microwave_source: keysight
        ip_address: '192.168.1.100'
        laser_channel: d_ch1
        microwave_blanking_channel: d_ch2
        i_channel: 0
        q_channel: 1

    """

    # cross connect in an I/Q capable MW source
    microwave_source = Connector(interface='MicrowaveModulationInterface')

    _ip_address = ConfigOption('ip_address', '169.254.8.2', missing='warn')
    _laser_channel = ConfigOption('laser_channel', 'd_ch1', missing='warn')
    _microwave_blanking_channel = ConfigOption('microwave_blanking_channel', 'd_ch2', missing='warn')
    _i_channel = ConfigOption('i_channel', '0', missing='warn')
    _q_channel = ConfigOption('q_channel', '1', missing='warn')
    _iq_voltage = ConfigOption('iq_voltage', 0.5, missing='nothing')

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)
        self.waveforms = dict()
        self._sequence = None
        self.current_status = 0
        self.sample_rate = 1e9
        self._pulse_ensemble = None
        self.pulse_streamer = None
        self._wfm = None
        self._laser_numeric = 0
        self._mw_numeric = 1
        self.i_channel = 0
        self.q_channel = 0
        self.iq_voltage = 0.5
        self.current_loaded_asset = ''
        self.current_ensemble = None
        self.current_ensemble_info = None
        self.current_pulse_blocks = dict()
        self.power_frac = 1.0

    def on_activate(self):
        """ Establish connection to pulse streamer and tell it to cancel all operations """

        self.sample_rate = 1e9
        self._pulse_ensemble = None
        self.iq_voltage = float(self._iq_voltage)
        self._laser_numeric = self.numeric_channel(self._laser_channel)
        self._mw_numeric = self.numeric_channel(self._microwave_blanking_channel)
        self.i_channel = self._i_channel
        self.q_channel = self._q_channel
        self.mw_source = self.microwave_source()

        #from unittest.mock import Mock
        #self.pulse_streamer = Mock()

        self.pulse_streamer = ps.PulseStreamer(self._ip_address)
        self.pulser_off()

    @property
    def laser_channel(self):
        return self._laser_numeric

    @property
    def laser_channel_qudi(self):
        return self.qudi_digital_channel(self._laser_numeric)

    @laser_channel.setter
    def laser_channel(self, value):
        ch_match = re.match(r'^d_ch(\d)$', value)
        if ch_match:
            self._laser_numeric = int(ch_match.group(1))-1
        elif value.isnumeric():
            self._laser_numeric = value
        else:
            self.log.error("Invalid laser channel {}".format(value))

    @property
    def microwave_blanking_channel(self):
        return self._mw_numeric

    @property
    def microwave_blanking_channel_qudi(self):
        return self.qudi_digital_channel(self._mw_numeric)

    @microwave_blanking_channel.setter
    def microwave_blanking_channel(self, value):
        ch_match = re.match(r'^d_ch(\d)$', value)
        if ch_match:
            self._mw_numeric = int(ch_match.group(1))-1
        elif value.isnumeric():
            self._mw_numeric = value
        else:
            self.log.error("Invalid microwave blanking channel {}".format(value))

    def on_deactivate(self):
        del self.pulse_streamer

    # Map Qudi channel names to numeric channel used by PulseStreamer
    @staticmethod
    def numeric_channel(channel_name):
        # 8 channels so one digit will do
        return int(channel_name[-1])-1

    # Map Qudi channel names to numeric channel used by PulseStreamer
    @staticmethod
    def qudi_digital_channel(channel_number):
        return 'd_ch{}'.format(channel_number+1)

    def get_constraints(self):
        constraints = PulserConstraints()

        constraints.waveform_format = []
        constraints.sequence_format = []
        constraints.sample_rate.min = 1e9
        constraints.sample_rate.max = 1e9
        constraints.sample_rate.step = 0
        constraints.sample_rate.default = 1e9

        constraints.d_ch_low.min = 0.0
        constraints.d_ch_low.max = 0.0
        constraints.d_ch_low.step = 0.0
        constraints.d_ch_low.default = 0.0

        constraints.d_ch_high.min = 3.3
        constraints.d_ch_high.max = 3.3
        constraints.d_ch_high.step = 0.0
        constraints.d_ch_high.default = 3.3

        # sample file length max is not well-defined for PulseStreamer, which collates sequential identical pulses into
        # one. Total number of not-sequentially-identical pulses which can be stored: 1 M.
        constraints.waveform_length.min = 1
        constraints.waveform_length.max = math.inf
        constraints.waveform_length.step = 1
        constraints.waveform_length.default = 1

        # the name a_ch<num> and d_ch<num> are generic names, which describe UNAMBIGUOUSLY the
        # channels. Here all possible channel configurations are stated, where only the generic
        # names should be used. The names for the different configurations can be customary chosen.
        activation_config = OrderedDict()
        activation_config['digital+iq'] = {'a_ch0'}.union({'d_ch{}'.format(n) for n in range(1, 9)})
        constraints.activation_config = activation_config

        return constraints

    def pulser_on(self):
        """ Switches the pulsing device on.

        @return int: error code (0:OK, -1:error)
        """
        # start the pulse sequence
        if self.current_ensemble is None:
            self.log.warn("Pulser cannot be started without loading a pulse sequence")
            return -1

        self.pulse_streamer.stream(self._sequence)
        self.log.info('Asset {} uploaded to PulseStreamer'.format(self.current_ensemble.name))
        #self.mw_source.turn_on_external_iq_modulation()
        time.sleep(0.2)
        self.pulse_streamer.startNow()
        self.current_status = 1
        return 0

    def pulser_off(self):
        """ Switches the pulsing device off.

        @return int: error code (0:OK, -1:error)
        """
        # stop the pulse sequence, set all channels LOW except laser and cw microwave x phase
        # set analogue outputs to 0V
        self.log.debug("Pulse mode off. Resetting output for non-pulse operation.")
        self.pulse_streamer.constant(([self.laser_channel, self.microwave_blanking_channel], 0.5, 0))
        self.log.debug("Laser channel {} set on".format(self.laser_channel))
        self.log.debug("Microwave blanking channel {} set on/transmissive".format(self.microwave_blanking_channel_qudi))
        self.log.debug("Turning off I/Q modulation")
        self.mw_source.turn_off_external_iq_modulation()
        self.current_status = 0
        return 0

    def get_status(self):
        """ Retrieves the status of the pulsing hardware

        @return (int, dict): tuple with an integer value of the current status
                             and a corresponding dictionary containing status
                             description for all the possible status variables
                             of the pulse generator hardware.
        """
        status_dic = dict()
        status_dic[-1] = 'Failed Request or Failed Communication with device.'
        status_dic[0] = 'Device has stopped, but can receive commands.'
        status_dic[1] = 'Device is active and running.'

        return self.current_status, status_dic

    def get_sample_rate(self):
        return self.sample_rate

    def set_sample_rate(self, sample_rate):
        self.log.debug('PulseStreamer sample rate cannot be configured')
        return self.sample_rate

    def get_analog_level(self, amplitude=None, offset=None):
        return {'a_ch0': 0}, {'a_ch0': 0}

    def set_analog_level(self, amplitude=None, offset=None):
        return self.get_analog_level()

    def get_digital_level(self, low=None, high=None):
        low_ch = low if low else PulseStreamer._digital_channels()
        high_ch = high if high else PulseStreamer._digital_channels()
        return {ch: 0 for ch in low_ch}, {ch: 3.3 for ch in high_ch}

    def set_digital_level(self, low=None, high=None):
        self.log.warning('PulseStreamer logic level cannot be adjusted!')
        return self.get_digital_level()

    @staticmethod
    def _digital_channels():
        return ['d_ch{}'.format(i) for i in range(1, 9)]

    @staticmethod
    def _all_channels():
        # note, the a_ch0 here is for Qudi's benefit and does not directly map to the two channels
        # used to control I/Q phase and amplitude. Using this channel for microwaves effectively this switches
        # on Sin analog pulses to parameterize I/Q modulation.
        return ['a_ch0'] + PulseStreamer._digital_channels()

    def get_active_channels(self,  ch=None):
        if ch is None or len(ch) < 1:
            return dict((k, True) for k in self._all_channels())
        else:
            return dict((k, True) for k in filter(k in self._all_channels() for k in ch))

    def set_active_channels(self, ch=None):
        return self.get_active_channels()

    def reset(self):
        self.pulser_off()
        return 0

    def set_pulse_ensemble(self, ensemble, ensemble_info=dict(), sequence_generator=None):
        # We're given the additional information needed to set up analogue channels
        self.log.debug("Setting ensemble: {}".format(ensemble))
        self.current_loaded_asset = ensemble.name
        self.current_ensemble = ensemble

        # assemble the RLE output for the 8 digital channels and 2 analog channels
        digital_output = [list() for _ in range(8)]
        analog_output = []

        # get the microwave control channel from the ensemble info
        microwave_gen_channel = sequence_generator.generation_parameters['microwave_channel']
        if microwave_gen_channel == 'a_ch0':
            # update the pulse blocks to open the blanking switch and show that explicitly
            for pulse_block_name, _ in ensemble.block_list:
                pulse_block = sequence_generator.get_block(pulse_block_name)
                for pbe in pulse_block:
                    pulse_function_type, pulse_function_params = self._pulse_function_type(pbe.pulse_function['a_ch0'])
                    if pulse_function_type == 'Sin':
                        microwave_on = True
                    else:
                        microwave_on = False
                    pbe.digital_high[self.qudi_digital_channel(self.microwave_blanking_channel)] = microwave_on
                sequence_generator.save_block(pulse_block)

        # Now actually generate the pulse sequence to upload
        for pulse_block_name, repetitions in ensemble.block_list:
            # reload - may have updated the blanking output channel
            pulse_block = sequence_generator.get_block(pulse_block_name)
            for n in range(1 + repetitions):  # horrible way to define the number of iterations ...
                for pbe in pulse_block:
                    length = int((pbe.init_length_s + pbe.increment_s * n)*1e9)

                    if microwave_gen_channel == 'a_ch0':
                        pulse_function_type, pulse_function_params = self._pulse_function_type(pbe.pulse_function['a_ch0'])
                        # "analogue" output i.e. IQ modulation control
                        if pulse_function_type == 'Sin':
                            # get the phase and amplitude to calculate I/Q values
                            phase_in_degrees = pulse_function_params['phase']
                            amplitude_in_dbm = pulse_function_params['amplitude']
                            amplitude_full = self.mw_source.get_power()
                            amplitude_fraction = math.pow(10, amplitude_in_dbm - amplitude_full)*.1
                            amplitude_fraction = self.power_frac
                            #self.log.debug("I/Q output amplitude fraction {}".format(amplitude_fraction))
                            phase_radians = phase_in_degrees/180*math.pi
                            iq_I = math.cos(phase_radians) * amplitude_fraction * self.iq_voltage
                            iq_Q = math.sin(phase_radians) * amplitude_fraction * self.iq_voltage
                            analog_output.append((length, iq_I, iq_Q))
                        else:
                            analog_output.append((length, 0, 0))

                    # state of digital channels - whether or not we're using the I/Q modulation
                    for ch, on in pbe.digital_high.items():
                        ch_n = self.numeric_channel(ch)
                        # override laser on
                        if ch_n == self.laser_channel:
                            digital_output[ch_n].append((length, 1 if pbe.laser_on else 0))
                        else:
                            digital_output[ch_n].append((length, 1 if on else 0))

            # Now concatenate analogue output instructions
            self.log.debug("Analogue prep {}".format(analog_output))
            zero_length = 0
            channel_i = []
            channel_q = []
            for length, iV, qV in analog_output:
                if iV == 0 and qV == 0:\
                    # rather than zeroing the I-Q output, change to the next output early and let the switch blank it
                    zero_length += length
                    continue
                else:
                    # output to the voltage arrays
                    channel_i.append((zero_length+length, iV))
                    channel_q.append((zero_length+length, qV))
                    zero_length = 0

        # ensures we initially switch early enough so the first pulse can settle

        # Finally set up the sequence
        self._sequence = self.pulse_streamer.createSequence()
        for ch in range(8):
            self._sequence.setDigital(ch, digital_output[ch])
            rising = 0
            falling = 0
            for a, b in pairwise(map(lambda x: x[1], digital_output[ch])):
                if a and not b:
                    falling += 1
                elif b and not a:
                    rising += 1

            self.log.debug("Digital channel {} has {} rising and {} falling".format(ch, rising, falling))
        self.log.debug("Set analog channels:\nanalog0{}\nanalog1{}".format(channel_i, channel_q))
        self._sequence.setAnalog(0, channel_i)
        self._sequence.setAnalog(1, channel_q)

        # We don't need any sampling done so just return True to signal that
        return True

    def load_waveform(self, load_dict):
        pass

    def load_sequence(self, sequence_name):
        pass

    def get_loaded_assets(self):
        asset = self.current_loaded_asset
        channels = [PulseStreamer.numeric_channel(ch) for ch, active in self.get_active_channels().items() if active]
        if asset is None:
            return dict(), None
        else:
            return {ch: asset for ch in channels}, 'waveform'

    def clear_all(self):
        self.current_loaded_asset = ''
        self.current_ensemble = None
        self.current_pulse_blocks = dict()

    def write_waveform(self, name, analog_samples, digital_samples, is_first_chunk, is_last_chunk, total_number_of_samples):
        return 0, []

    def write_sequence(self, name, sequence_parameters):
        return 0, []

    def get_waveform_names(self):
        return []

    def get_sequence_names(self):
        return []

    def delete_waveform(self, waveform_name):
        pass

    def delete_sequence(self, sequence_name):
        pass

    def get_interleave(self):
        return False

    def set_interleave(self, state=False):
        pass

    @staticmethod
    def _pulse_function_type(pf):
        # type of pulse_function doesn't compare normally as a type for some reason so take a circuitous route
        pulse_function_dict = pf.get_dict_representation()
        return pulse_function_dict['name'], pulse_function_dict['params']

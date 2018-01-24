# -*- coding: utf-8 -*-

"""
This file contains the Qudi hardware file to control R&S SMBV100A microwave device.

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

Parts of this file were developed from a PI3diamond module which is
Copyright (C) 2009 Helmut Rathgen <helmut.rathgen@gmail.com>

Copyright (c) the Qudi Developers. See the COPYRIGHT.txt file at the
top-level directory of this distribution and at <https://github.com/Ulm-IQO/qudi/>
"""

import visa
import time

from core.module import Base, ConfigOption
from interface.microwave_interface import MicrowaveInterface
from interface.microwave_interface import MicrowaveLimits
from interface.microwave_interface import MicrowaveMode
from interface.microwave_interface import TriggerEdge


class MicrowaveSGS(Base, MicrowaveInterface):
    """ This is the Interface class to define the controls for the simple
        microwave hardware.
    """

    _modclass = 'MicrowaveSGS'
    _modtype = 'hardware'

    _address = ConfigOption('address', missing='error')
    _timeout = ConfigOption('timeout', 10, missing='warn')

    _mode = 'cw'
    _sweep_parameters = None
    _sweep_index = None

    # Indicate how fast frequencies within a list or sweep mode can be changed:
    _FREQ_SWITCH_SPEED = 0.003  # Frequency switching speed in s (acc. to specs)

    def on_activate(self):
        """ Initialisation performed during activation of the module. """
        self._timeout = self._timeout * 1000
        # trying to load the visa connection to the module
        self.rm = visa.ResourceManager()
        try:
            self._connection = self.rm.open_resource(self._address,
                                                     timeout=self._timeout)
        except:
            self.log.error('Could not connect to LAN address >>{}<<.'.format(self._address))
            raise

        self.log.info('MW SGS100A initialised and connected to hardware.')
        self.model = self._connection.query('*IDN?').split(',')[1]
        self._command_wait('*CLS')
        self._command_wait('*RST')
        return

    def on_deactivate(self):
        """ Cleanup performed during deactivation of the module. """
        self._connection.close()
        return

    def _command_wait(self, command_str):
        """
        Writes the command in command_str via GPIB and waits until the device has finished
        processing it.

        @param command_str: The command to be written
        """
        self._connection.write(command_str)
        # self._connection.write('*WAI')
        while int(float(self._connection.query('*OPC?'))) != 1:
            time.sleep(0.2)
        return

    def get_limits(self):
        """ Create an object containing parameter limits for this microwave source.

            @return MicrowaveLimits: device-specific parameter limits
        """
        limits = MicrowaveLimits()
        limits.supported_modes = (MicrowaveMode.CW, MicrowaveMode.SWEEP)

        limits.min_power = -145
        limits.max_power = 30

        limits.min_frequency = 1e6
        limits.max_frequency = 6e9

        limits.list_minstep = 0.1
        limits.list_maxstep = 5.991e9
        limits.list_maxentries = 1

        limits.sweep_minstep = 0.1
        limits.sweep_maxstep = 5.991e9
        limits.sweep_maxentries = 10001

        if self.model != 'SGS100A':
            self.log.warning('Model string unknown, hardware limits may be wrong.')

        return limits

    def off(self):
        """
        Switches off any microwave output.
        Must return AFTER the device is actually stopped.

        @return int: error code (0:OK, -1:error)
        """
        mode, is_running = self.get_status()
        if not is_running:
            return 0

        self._connection.write('OUTP:STAT OFF')
        # self._connection.write('*WAI')
        while int(float(self._connection.query('OUTP:STAT?'))) != 0:
            time.sleep(0.2)
        return 0

    def get_status(self):
        """
        Gets the current status of the MW source, i.e. the mode (cw, list or sweep) and
        the output state (stopped, running)

        @return str, bool: mode ['cw', 'list', 'sweep'], is_running [True, False]
        """
        is_running = bool(int(float(self._connection.query('OUTP:STAT?'))))

        # the SGS100A is capable only of CW mode, but we can "fake" a sweep mode using the software
        # trigger option. thus, asking the hardware for the current mode is incorrect - we must keep
        # keep track of it ourselves.
        mode = self._mode
        return mode, is_running

    def get_power(self):
        """
        Gets the microwave output power.

        @return float: the power set at the device in dBm
        """
        return float(self._connection.query(':POW?'))

    def get_frequency(self):
        """
        Gets the frequency of the microwave output.
        Returns single float value if the device is in cw mode.
        Returns list like [start, stop, step] if the device is in sweep mode.
        Returns list of frequencies if the device is in list mode.

        @return [float, list]: frequency(s) currently set for this device in Hz
        """
        mode, is_running = self.get_status()
        if 'cw' in mode:
            return float(self._connection.query(':FREQ?'))
        elif 'sweep' in mode:
            return self._sweep_parameters

    def cw_on(self):
        """
        Switches on cw microwave output.
        Must return AFTER the device is actually running.

        @return int: error code (0:OK, -1:error)
        """
        current_mode, is_running = self.get_status()
        if is_running:
            if current_mode == 'cw':
                return 0
            else:
                self.off()

        if current_mode != 'cw':
            self._command_wait(':FREQ:MODE CW')

        self._connection.write(':OUTP:STAT ON')
        # self._connection.write('*WAI')
        dummy, is_running = self.get_status()
        while not is_running:
            time.sleep(0.2)
            dummy, is_running = self.get_status()
        return 0

    def set_cw(self, frequency=None, power=None, set_mode=True):
        """
        Configures the device for cw-mode and optionally sets frequency and/or power

        @param float frequency: frequency to set in Hz
        @param float power: power to set in dBm
        @param bool set_mode: whether or not to update the internal mode to 'cw' (as hardware is always running cw)

        @return tuple(float, float, str): with the relation
            current frequency in Hz,
            current power in dBm,
            current mode
        """
        mode, is_running = self.get_status()
        if is_running:
            self.off()

        # Set CW frequency
        if frequency is not None:
            self._command_wait(':FREQ {0:f}'.format(frequency))

        # Set CW power
        if power is not None:
            self._command_wait(':POW {0:f}'.format(power))

        if set_mode is True:
            self._mode = 'cw'

        # Return set values
        mode, _ = self.get_status()
        actual_freq = self.get_frequency()
        actual_power = self.get_power()
        return actual_freq, actual_power, mode

    def list_on(self):
        """
        Switches on the list mode microwave output.
        Must return AFTER the device is actually running.

        @return int: error code (0:OK, -1:error)
        """
        self.log.error('List mode not available for this microwave hardware!')
        return -1

    def set_list(self, frequency=None, power=None):
        """
        Configures the device for list-mode and optionally sets frequencies and/or power

        @param list frequency: list of frequencies in Hz
        @param float power: MW power of the frequency list in dBm

        @return tuple(list, float, str):
            current frequencies in Hz,
            current power in dBm,
            current mode
        """
        self.log.error('List mode not available for this microwave hardware!')
        return -1

    def reset_listpos(self):
        """
        Reset of MW list mode position to start (first frequency step)

        @return int: error code (0:OK, -1:error)
        """
        self.log.error('List mode not available for this microwave hardware!')
        return -1

    def sweep_on(self):
        """ Switches on the sweep mode.

        @return int: error code (0:OK, -1:error)
        """
        current_mode, is_running = self.get_status()
        if is_running:
            if current_mode == 'sweep':
                return 0
            else:
                self.off()

        self._connection.write(':OUTP:STAT ON')
        _, is_running = self.get_status()
        while not is_running:
            time.sleep(0.2)
            dummy, is_running = self.get_status()
        return 0

    def set_sweep(self, start=None, stop=None, step=None, power=None):
        """
        Configures the device for sweep-mode and optionally sets frequency start/stop/step
        and/or power

        @return float, float, float, float, str: current start frequency in Hz,
                                                 current stop frequency in Hz,
                                                 current frequency step in Hz,
                                                 current power in dBm,
                                                 current mode
        """
        mode, is_running = self.get_status()
        if is_running:
            self.off()

        if start is not None:
            self._sweep_parameters = [start, stop, step]
            number_of_points = (stop - start) / step + 1
            self._sweep_index = [0, number_of_points]

        if power is not None:
            self.set_cw(power=power)

        self.set_cw(frequency=start)

        self._mode = 'sweep'

        actual_power = self.get_power()
        freq_list = self.get_frequency()
        mode, _ = self.get_status()
        return freq_list[0], freq_list[1], freq_list[2], actual_power, mode

    def _compute_frequency_from_sweep_index(self, index):
        fstart, _, fstep = self._sweep_parameters
        return fstart + fstep*index

    def _activate_sweep_point(self, index):
        frequency = self._compute_frequency_from_sweep_index(index)
        _, limit_index = self._sweep_index
        self._sweep_index = [index, limit_index]
        self.set_cw(frequency=frequency, set_mode=False)

    def reset_sweeppos(self):
        """
        Reset of MW sweep mode position to start (start frequency)

        @return int: error code (0:OK, -1:error)
        """
        if self._sweep_parameters is not None:
            self._activate_sweep_point(0)
        return 0

    def set_ext_trigger(self, pol=TriggerEdge.RISING):
        """ Set the external trigger for this device with proper polarization.

        @param TriggerEdge pol: polarisation of the trigger (basically rising edge or falling edge)

        @return object: current trigger polarity [TriggerEdge.RISING, TriggerEdge.FALLING]
        """
        self.log.warning('SGS100A hardware does not support hardware triggering')
        return pol

    def set_trigger_pol(self, pol):
        return self.set_ext_trigger(self ,pol)

    def trigger(self):
        """ Trigger the next element in the list or sweep mode programmatically.

        @return int: error code (0:OK, -1:error)

        Ensure that the Frequency was set AFTER the function returns, or give
        the function at least a save waiting time.
        """
        current_index, limit_index = self._sweep_index
        if current_index + 1 == limit_index:
            new_index = 0
        else:
            new_index = current_index + 1
        self._activate_sweep_point(new_index)

        time.sleep(self._FREQ_SWITCH_SPEED)  # that is the switching speed
        return 0
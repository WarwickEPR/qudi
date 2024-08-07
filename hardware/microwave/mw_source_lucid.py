# -*- coding: utf-8 -*-

"""
This file contains the Qudi hardware file to control R&S SMB100A or SMBV100A microwave device.

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

import time
import comtypes
import comtypes.client

from core.module import Base
from core.configoption import ConfigOption
from interface.microwave_interface import MicrowaveInterface
from interface.microwave_interface import MicrowaveLimits
from interface.microwave_interface import MicrowaveMode
from interface.microwave_interface import TriggerEdge

# not sure why the first three here don't seem to be needed...
# comtypes.client.GetModule("IviDriverTypeLib.dll")
# comtypes.client.GetModule("IviRFSiggenTypeLib.dll")
# comtypes.client.GetModule("ls129x_64.dll")
# from comtypes.gen import LS129xLib


class MicrowaveLucid(Base, MicrowaveInterface):
    """ Hardware file to control a Tabor Lucid microwave device.

    Example config for copy-paste:

    mw_source_lucid:
        module.Class: 'microwave.mw_source_lucid.MicrowaveLucid'
        max_power: 0
    """

    # to limit the power to a lower value that the hardware can provide
    _max_power = ConfigOption('max_power', missing='error')

    # Indicate how fast frequencies within a list or sweep mode can be changed:
    _FREQ_SWITCH_SPEED = 100e-6  # Frequency switching speed in s (acc. to specs, for Fast Switching option)

    def on_activate(self):
        """ Initialisation performed during activation of the module. """
        try:
            self.lucid = comtypes.client.CreateObject("LS129x.LS129x")
            self.lucid.Initialize('', False, False, '')
            self.lucid.RF.RFConfigure(0.5e9, -30)
        except:
            self.log.error('Could not connect to the lucid microwave generator')
            raise

        self.log.info('Lucid generator initialised and connected.')

        limits = self.get_limits()
        self.set_cw(power=limits.min_power)
        return

    def on_deactivate(self):
        """ Cleanup performed during deactivation of the module. """
        self.off()
        self.lucid.Close()
        return

    def _command_wait(self, command_str):
        """
        Writes the command in command_str via resource manager and waits until the device has finished
        processing it.

        @param command_str: The command to be written
        """
        self._connection.write(command_str)
        self._connection.write('*WAI')
        while int(float(self._connection.query('*OPC?'))) != 1:
            time.sleep(0.2)
        return

    def get_limits(self):
        """ Create an object containing parameter limits for this microwave source.

            @return MicrowaveLimits: device-specific parameter limits
        """
        limits = MicrowaveLimits()
        limits.supported_modes = (MicrowaveMode.CW, MicrowaveMode.SWEEP)
        # TODO note that the generators also support list, which is yet to be implemented

        # values for LS6081D
        limits.min_power = -30
        limits.max_power = +15

        limits.min_frequency = 9e3
        limits.max_frequency = 6e9

        limits.list_minstep = 0.1
        limits.list_maxstep = limits.max_frequency - limits.min_frequency
        limits.list_maxentries = 4096

        limits.sweep_minstep = 0.1
        limits.sweep_maxstep = limits.max_frequency - limits.min_frequency
        limits.sweep_maxentries = 65535

        # limit to a maximum set in config file
        if self._max_power is not None and self._max_power < limits.max_power:
            limits.max_power = self._max_power

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

        self.lucid.RF.OutputEnabled = False
        while self.lucid.RF.OutputEnabled is True:
            time.sleep(0.2)
        return 0

    def get_status(self):
        """
        Gets the current status of the MW source, i.e. the mode (cw, list or sweep) and
        the output state (stopped, running)

        @return str, bool: mode ['cw', 'list', 'sweep'], is_running [True, False]
        """
        is_running = self.lucid.RF.OutputEnabled
        is_sweep = self.lucid.Sweep.FrequencySweep.Enabled
        if is_sweep is True:
            mode = 'sweep'
        else:
            mode = 'cw'
        return mode, is_running

    def get_power(self):
        """
        Gets the microwave output power.

        @return float: the power set at the device in dBm
        """
        # This case works for cw AND sweep mode
        return self.lucid.RF.Level

    def get_frequency(self):
        """
        Gets the frequency of the microwave output.
        Returns single float value if the device is in cw mode.
        Returns list like [start, stop, step] if the device is in sweep mode.
        Returns list of frequencies if the device is in list mode.

        @return [float, list]: frequency(s) currently set for this device in Hz
        """
        mode, _ = self.get_status()
        if 'cw' in mode:
            return_val = self.lucid.RF.Frequency
        elif 'sweep' in mode:
            start = self.lucid.Sweep.FrequencySweep.Start
            stop = self.lucid.Sweep.FrequencySweep.Stop
            n_steps = self.lucid.Sweep.FrequencySweep.Step
            step = (stop - start) / (float(n_steps - 1))
            return_val = [start, stop, step]

        return return_val

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
            self.lucid.Sweep.FrequencySweep.Enabled = False

        self.lucid.RF.OutputEnabled = True
        _, is_running = self.get_status()
        while not is_running:
            time.sleep(0.2)
            _, is_running = self.get_status()
        return 0

    def set_cw(self, frequency=None, power=None):
        """
        Configures the device for cw-mode and optionally sets frequency and/or power

        @param float frequency: frequency to set in Hz
        @param float power: power to set in dBm

        @return tuple(float, float, str): with the relation
            current frequency in Hz,
            current power in dBm,
            current mode
        """
        mode, is_running = self.get_status()
        if is_running:
            self.off()

        # Activate CW mode
        if mode != 'cw':
            self.lucid.Sweep.FrequencySweep.Enabled = False

        # Set CW frequency
        if frequency is not None:
            self.lucid.RF.Frequency = frequency

        # Set CW power
        if power is not None:
            self.lucid.RF.Level = power

        # Return actually set values
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
        mode, _ = self.get_status()
        return self.get_frequency(), self.get_power(), mode

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

        if current_mode != 'sweep':
            self.lucid.Sweep.FrequencySweep.Enabled = True

        self.lucid.RF.OutputEnabled = True
        _, is_running = self.get_status()
        while not is_running:
            time.sleep(0.2)
            _, is_running = self.get_status()
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

        if mode != 'sweep':
            self.lucid.Sweep.FrequencySweep.Enabled = True

        if (start is not None) and (stop is not None) and (step is not None):
            self.lucid.Sweep.FrequencySweep.Start = start
            self.lucid.Sweep.FrequencySweep.Stop = stop
            n_steps = int((stop - start) / step) + 1
            self.lucid.Sweep.FrequencySweep.Step = n_steps

        if power is not None:
            self.lucid.RF.Level = power

        self.lucid.Trigger.Advance = 1 #frequency step per trigger

        actual_power = self.get_power()
        freq_list = self.get_frequency()
        mode, _ = self.get_status()
        return freq_list[0], freq_list[1], freq_list[2], actual_power, mode

    def reset_sweeppos(self):
        """
        Reset of MW sweep mode position to start (start frequency)

        @return int: error code (0:OK, -1:error)
        """
        self.lucid.Sweep.FrequencySweep.Enabled = False
        self.lucid.Sweep.FrequencySweep.Enabled = True
        return 0

    def set_ext_trigger(self, pol, timing):
        """ Set the external trigger for this device with proper polarization.

        @param TriggerEdge pol: polarisation of the trigger (basically rising edge or falling edge)
        @param float timing: estimated time between triggers

        @return object, float: current trigger polarity [TriggerEdge.RISING, TriggerEdge.FALLING],
            trigger timing
        """
        _, is_running = self.get_status()
        if is_running:
            self.off()

        if pol == TriggerEdge.RISING:
            self.lucid.Trigger.Edge = 0
        elif pol == TriggerEdge.FALLING:
            self.lucid.Trigger.Edge = 1
        else:
            self.log.warning('No valid trigger polarity passed to microwave hardware module.')
            edge = None

        self.lucid.Trigger.Source = 0 #external

        polarity = self.lucid.Trigger.Edge
        if polarity == 1:
            return TriggerEdge.FALLING, timing
        else:
            return TriggerEdge.RISING, timing

    def trigger(self):
        """ Trigger the next element in the list or sweep mode programmatically.

        @return int: error code (0:OK, -1:error)

        Ensure that the Frequency was set AFTER the function returns, or give
        the function at least a save waiting time.
        """

        # WARNING:
        # The manual trigger functionality was not tested for this device!
        # Might not work well! Please check that!
        self.lucid.Trigger.SendSoftwareTrigger()
        time.sleep(self._FREQ_SWITCH_SPEED)  # that is the switching speed
        return 0

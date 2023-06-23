# -*- coding: utf-8 -*-
from qtpy import QtCore
from collections import OrderedDict
from interface.microwave_interface import MicrowaveMode
from interface.microwave_interface import TriggerEdge
import numpy as np
import time
import datetime
import matplotlib.pyplot as plt

from logic.generic_logic import GenericLogic
from core.util.mutex import Mutex
from core.connector import Connector
from core.configoption import ConfigOption
from core.statusvariable import StatusVar


class PDMRLogic(GenericLogic):
    """This is the Logic class for PDMR."""

    # declare connectors
    pdmrcounter = Connector(interface='PDMRCounterInterface')
    fitlogic = Connector(interface='FitLogic')
    microwave1 = Connector(interface='MicrowaveInterface')
    savelogic = Connector(interface='SaveLogic')
    taskrunner = Connector(interface='TaskRunner')

    # config option
    mw_scanmode = ConfigOption(
        'scanmode',
        'LIST',
        missing='warn',
        converter=lambda x: MicrowaveMode[x.upper()])

    clock_frequency = StatusVar('clock_frequency', 200)
    cw_mw_frequency = StatusVar('cw_mw_frequency', 2870e6)
    cw_mw_power = StatusVar('cw_mw_power', -30)
    sweep_mw_power = StatusVar('sweep_mw_power', -30)
    fit_range = StatusVar('fit_range', 0)
    mw_starts = StatusVar('mw_starts', [2800e6])
    mw_stops = StatusVar('mw_stops', [2950e6])
    mw_steps = StatusVar('mw_steps', [2e6])
    run_time = StatusVar('run_time', 60)
    number_of_lines = StatusVar('number_of_lines', 50)
    ranges = StatusVar('ranges', 1)
    fc = StatusVar('fits', None)
    lines_to_average = StatusVar('lines_to_average', 0)
    _oversampling = StatusVar('oversampling', default=10)
    _lock_in_active = StatusVar('lock_in_active', default=False)

    # Internal signals
    sigNextLine = QtCore.Signal()

    # Update signals, e.g. for GUI module
    sigParameterUpdated = QtCore.Signal(dict)
    sigOutputStateUpdated = QtCore.Signal(str, bool)
    sigPdmrPlotsUpdated = QtCore.Signal(np.ndarray, np.ndarray, np.ndarray)
    sigPdmrFitUpdated = QtCore.Signal(np.ndarray, np.ndarray, dict, str)
    sigPdmrElapsedTimeUpdated = QtCore.Signal(float, int)

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)
        self.threadlock = Mutex()

    def on_activate(self):
        """
        Initialisation performed during activation of the module.
        """
        # Get connectors
        self._mw_device = self.microwave1()
        self._fit_logic = self.fitlogic()
        self._pdmr_counter = self.pdmrcounter()
        self._save_logic = self.savelogic()
        self._taskrunner = self.taskrunner()

        # Get hardware constraints
        limits = self.get_hw_constraints()

        # Set/recall microwave source parameters
        self.cw_mw_frequency = limits.frequency_in_range(self.cw_mw_frequency)
        self.cw_mw_power = limits.power_in_range(self.cw_mw_power)
        self.sweep_mw_power = limits.power_in_range(self.sweep_mw_power)
        self._pdmr_counter.oversampling = self._oversampling
        self._pdmr_counter.lock_in_active = self._lock_in_active

        # Set the trigger polarity (RISING/FALLING) of the mw-source input trigger
        # theoretically this can be changed, but the current counting scheme will not support that
        self.mw_trigger_pol = TriggerEdge.RISING
        self.set_trigger(self.mw_trigger_pol, self.clock_frequency)

        # Elapsed measurement time and number of sweeps
        self.elapsed_time = 0.0
        self.elapsed_sweeps = 0

        self.range_to_fit = 0
        self.matrix_range = 0
        self.fits_performed = {}

        self.frequency_lists = []
        self.final_freq_list = []

        # Set flags
        # for stopping a measurement
        self._stopRequested = False
        # for clearing the PDMR data during a measurement
        self._clearPdmrData = False

        # Initalize the PDMR data arrays (mean signal and sweep matrix)
        self._initialize_pdmr_plots()
        # Raw data array
        self.pdmr_raw_data = np.zeros(
            [self.number_of_lines,
             len(self._pdmr_counter.get_pdmr_channels()),
             self.pdmr_plot_x.size]
        )

        # Switch off microwave and set CW frequency and power
        self.mw_off()
        self.set_cw_parameters(self.cw_mw_frequency, self.cw_mw_power)

        # Connect signals
        self.sigNextLine.connect(self._scan_pdmr_line, QtCore.Qt.QueuedConnection)
        return

    def on_deactivate(self):
        """ Deinitialisation performed during deactivation of the module.
        """
        # Stop measurement if it is still running
        if self.module_state() == 'locked':
            self.stop_pdmr_scan()
        timeout = 30.0
        start_time = time.time()
        while self.module_state() == 'locked':
            time.sleep(0.5)
            timeout -= (time.time() - start_time)
            if timeout <= 0.0:
                self.log.error('Failed to properly deactivate pdmr logic. Pdmr scan is still '
                               'running but can not be stopped after 30 sec.')
                break
        # Switch off microwave source for sure (also if CW mode is active or module is still locked)
        self._mw_device.off()
        # Disconnect signals
        self.sigNextLine.disconnect()

    @fc.constructor
    def sv_set_fits(self, val):
        # Setup fit container
        fc = self.fitlogic().make_fit_container('PDMR sum', '1d')
        fc.set_units(['Hz', 'A'])
        if isinstance(val, dict) and len(val) > 0:
            fc.load_from_dict(val)
        else:
            d1 = OrderedDict()
            d1['Lorentzian dip'] = {
                'fit_function': 'lorentzian',
                'estimator': 'dip'
            }
            d1['Two Lorentzian dips'] = {
                'fit_function': 'lorentziandouble',
                'estimator': 'dip'
            }
            d1['N14'] = {
                'fit_function': 'lorentziantriple',
                'estimator': 'N14'
            }
            d1['N15'] = {
                'fit_function': 'lorentziandouble',
                'estimator': 'N15'
            }
            d1['Two Gaussian dips'] = {
                'fit_function': 'gaussiandouble',
                'estimator': 'dip'
            }
            default_fits = OrderedDict()
            default_fits['1d'] = d1
            fc.load_from_dict(default_fits)
        return fc

    @fc.representer
    def sv_get_fits(self, val):
        """ save configured fits """
        if len(val.fit_list) > 0:
            return val.save_to_dict()
        else:
            return None

    def _initialize_pdmr_plots(self):
        """ Initializing the PDMR plots (line and matrix). """

        final_freq_list = []
        self.frequency_lists = []
        for mw_start, mw_stop, mw_step in zip(self.mw_starts, self.mw_stops, self.mw_steps):
            freqs = np.arange(mw_start, mw_stop + mw_step, mw_step)
            final_freq_list.extend(freqs)
            self.frequency_lists.append(freqs)

        if type(self.final_freq_list) == list:
            self.final_freq_list = np.array(final_freq_list)

        self.pdmr_plot_x = np.array(self.final_freq_list)
        self.pdmr_plot_y = np.zeros([len(self.get_pdmr_channels()), self.pdmr_plot_x.size])

        self.pdmr_plot_xy = np.zeros(
            [self.number_of_lines, len(self.get_pdmr_channels()), self.pdmr_plot_x.size])

        range_to_fit = self.range_to_fit

        self.pdmr_fit_x = np.arange(self.mw_starts[range_to_fit],
                                    self.mw_stops[range_to_fit] + self.mw_steps[range_to_fit],
                                    self.mw_steps[range_to_fit])

        self.pdmr_fit_y = np.zeros(self.pdmr_fit_x.size)

        self.sigPdmrPlotsUpdated.emit(self.pdmr_plot_x, self.pdmr_plot_y, self.pdmr_plot_xy)
        current_fit = self.fc.current_fit
        self.sigPdmrFitUpdated.emit(self.pdmr_fit_x, self.pdmr_fit_y, {}, current_fit)
        return

    def set_trigger(self, trigger_pol, frequency):
        """
        Set trigger polarity of external microwave trigger (for list and sweep mode).

        @param object trigger_pol: one of [TriggerEdge.RISING, TriggerEdge.FALLING]
        @param float frequency: trigger frequency during PDMR scan

        @return object: actually set trigger polarity returned from hardware
        """
        if self._lock_in_active:
            frequency = frequency / self._oversampling

        if self.module_state() != 'locked':
            self.mw_trigger_pol, triggertime = self._mw_device.set_ext_trigger(trigger_pol, 1 / frequency)
        else:
            self.log.warning('set_trigger failed. Logic is locked.')

        update_dict = {'trigger_pol': self.mw_trigger_pol}
        self.sigParameterUpdated.emit(update_dict)
        return self.mw_trigger_pol

    def set_average_length(self, lines_to_average):
        """
        Sets the number of lines to average for the sum of the data

        @param int lines_to_average: desired number of lines to average (0 means all)

        @return int: actually set lines to average
        """
        self.lines_to_average = int(lines_to_average)

        if self.lines_to_average <= 0:
            self.pdmr_plot_y = np.mean(
                self.pdmr_raw_data[:max(1, self.elapsed_sweeps), :, :],
                axis=0,
                dtype=np.float64
            )
        else:
            self.pdmr_plot_y = np.mean(
                self.pdmr_raw_data[:max(1, min(self.lines_to_average, self.elapsed_sweeps)), :, :],
                axis=0,
                dtype=np.float64
            )

        self.sigPdmrPlotsUpdated.emit(self.pdmr_plot_x, self.pdmr_plot_y, self.pdmr_plot_xy)
        self.sigParameterUpdated.emit({'average_length': self.lines_to_average})
        return self.lines_to_average

    def set_clock_frequency(self, clock_frequency):
        """
        Sets the frequency of the counter clock

        @param int clock_frequency: desired frequency of the clock

        @return int: actually set clock frequency
        """
        # checks if scanner is still running
        if self.module_state() != 'locked' and isinstance(clock_frequency, (int, float)):
            self.clock_frequency = int(clock_frequency)
        else:
            self.log.warning('set_clock_frequency failed. Logic is either locked or input value is '
                             'no integer or float.')

        update_dict = {'clock_frequency': self.clock_frequency}
        self.sigParameterUpdated.emit(update_dict)
        return self.clock_frequency

    @property
    def oversampling(self):
        return self._oversampling

    @oversampling.setter
    def oversampling(self, oversampling):
        """
        Sets the frequency of the counter clock

        @param int oversampling: desired oversampling per frequency step
        """
        # checks if scanner is still running
        if self.module_state() != 'locked' and isinstance(oversampling, (int, float)):
            self._oversampling = int(oversampling)
            self._pdmr_counter.oversampling = self._oversampling
        else:
            self.log.warning('setter of oversampling failed. Logic is either locked or input value is '
                             'no integer or float.')

        update_dict = {'oversampling': self._oversampling}
        self.sigParameterUpdated.emit(update_dict)

    def set_oversampling(self, oversampling):
        self.oversampling = oversampling
        return self.oversampling

    @property
    def lock_in(self):
        return self._lock_in_active

    @lock_in.setter
    def lock_in(self, active):
        """
        Sets the frequency of the counter clock

        @param bool active: specify if signal should be detected with lock in
        """
        # checks if scanner is still running
        if self.module_state() != 'locked' and isinstance(active, bool):
            self._lock_in_active = active
            self._pdmr_counter.lock_in_active = self._lock_in_active
        else:
            self.log.warning('setter of lock in failed. Logic is either locked or input value is no boolean.')

        update_dict = {'lock_in': self._lock_in_active}
        self.sigParameterUpdated.emit(update_dict)

    def set_lock_in(self, active):
        self.lock_in = active
        return self.lock_in

    def set_matrix_line_number(self, number_of_lines):
        """
        Sets the number of lines in the PDMR matrix

        @param int number_of_lines: desired number of matrix lines

        @return int: actually set number of matrix lines
        """
        if isinstance(number_of_lines, int):
            self.number_of_lines = number_of_lines
        else:
            self.log.warning('set_matrix_line_number failed. '
                             'Input parameter number_of_lines is no integer.')

        update_dict = {'number_of_lines': self.number_of_lines}
        self.sigParameterUpdated.emit(update_dict)
        return self.number_of_lines

    def set_runtime(self, runtime):
        """
        Sets the runtime for PDMR measurement

        @param float runtime: desired runtime in seconds

        @return float: actually set runtime in seconds
        """
        if isinstance(runtime, (int, float)):
            self.run_time = runtime
        else:
            self.log.warning('set_runtime failed. Input parameter runtime is no integer or float.')

        update_dict = {'run_time': self.run_time}
        self.sigParameterUpdated.emit(update_dict)
        return self.run_time

    def set_cw_parameters(self, frequency, power):
        """ Set the desired new cw mode parameters.

        @param float frequency: frequency to set in Hz
        @param float power: power to set in dBm

        @return (float, float): actually set frequency in Hz, actually set power in dBm
        """
        if self.module_state() != 'locked' and isinstance(frequency, (int, float)) and isinstance(power, (int, float)):
            constraints = self.get_hw_constraints()
            frequency_to_set = constraints.frequency_in_range(frequency)
            power_to_set = constraints.power_in_range(power)
            self.cw_mw_frequency, self.cw_mw_power, dummy = self._mw_device.set_cw(frequency_to_set,
                                                                                   power_to_set)
        else:
            self.log.warning('set_cw_frequency failed. Logic is either locked or input value is '
                             'no integer or float.')

        param_dict = {'cw_mw_frequency': self.cw_mw_frequency, 'cw_mw_power': self.cw_mw_power}
        self.sigParameterUpdated.emit(param_dict)
        return self.cw_mw_frequency, self.cw_mw_power

    def set_sweep_parameters(self, starts, stops, steps, power):
        """ Set the desired frequency parameters for list and sweep mode

        @param list starts: list of start frequencies to set in Hz
        @param list stops: list of stop frequencies to set in Hz
        @param list steps: list of step frequencies to set in Hz
        @param list power: mw power to set in dBm

        @return list, list, list, float: current start_freq, current stop_freq,
                                            current freq_step, current power
        """
        limits = self.get_hw_constraints()
        # as everytime all the elements are read when editing of a box is finished
        # also need to reset the lists in this case
        self.mw_starts = []
        self.mw_steps = []
        self.mw_stops = []

        if self.module_state() != 'locked':
            for start, step, stop in zip(starts, steps, stops):
                if isinstance(start, (int, float)):
                    self.mw_starts.append(limits.frequency_in_range(start))
                if isinstance(stop, (int, float)) and isinstance(step, (int, float)):
                    if stop <= start:
                        stop = start + step
                    self.mw_stops.append(limits.frequency_in_range(stop))
                    if self.mw_scanmode == MicrowaveMode.LIST:
                        self.mw_steps.append(limits.list_step_in_range(step))
                    elif self.mw_scanmode == MicrowaveMode.SWEEP:
                        if self.ranges == 1:
                            self.mw_steps.append(limits.sweep_step_in_range(step))
                        else:
                            self.log.error("Sweep mode will only work with one frequency range.")

            if isinstance(power, (int, float)):
                self.sweep_mw_power = limits.power_in_range(power)
        else:
            self.log.warning('set_sweep_parameters failed. Logic is locked.')

        param_dict = {'mw_starts': self.mw_starts, 'mw_stops': self.mw_stops, 'mw_steps': self.mw_steps,
                      'sweep_mw_power': self.sweep_mw_power}
        self.sigParameterUpdated.emit(param_dict)
        return self.mw_starts, self.mw_stops, self.mw_steps, self.sweep_mw_power

    def mw_cw_on(self):
        """
        Switching on the mw source in cw mode.

        @return str, bool: active mode ['cw', 'list', 'sweep'], is_running
        """
        if self.module_state() == 'locked':
            self.log.error('Can not start microwave in CW mode. PDMRLogic is already locked.')
        else:
            self.cw_mw_frequency, \
            self.cw_mw_power, \
            mode = self._mw_device.set_cw(self.cw_mw_frequency, self.cw_mw_power)
            param_dict = {'cw_mw_frequency': self.cw_mw_frequency, 'cw_mw_power': self.cw_mw_power}
            self.sigParameterUpdated.emit(param_dict)
            if mode != 'cw':
                self.log.error('Switching to CW microwave output mode failed.')
            else:
                err_code = self._mw_device.cw_on()
                if err_code < 0:
                    self.log.error('Activation of microwave output failed.')

        mode, is_running = self._mw_device.get_status()
        self.sigOutputStateUpdated.emit(mode, is_running)
        return mode, is_running

    def mw_sweep_on(self):
        """
        Switching on the mw source in list/sweep mode.

        @return str, bool: active mode ['cw', 'list', 'sweep'], is_running
        """

        limits = self.get_hw_constraints()
        param_dict = {}
        self.final_freq_list = []
        if self.mw_scanmode == MicrowaveMode.LIST:
            final_freq_list = []
            used_starts = []
            used_steps = []
            used_stops = []
            for mw_start, mw_stop, mw_step in zip(self.mw_starts, self.mw_stops, self.mw_steps):
                num_steps = int(np.rint((mw_stop - mw_start) / mw_step))
                end_freq = mw_start + num_steps * mw_step
                freq_list = np.linspace(mw_start, end_freq, num_steps + 1)

                # adjust the end frequency in order to have an integer multiple of step size
                # The master module (i.e. GUI) will be notified about the changed end frequency
                final_freq_list.extend(freq_list)

                used_starts.append(mw_start)
                used_steps.append(mw_step)
                used_stops.append(end_freq)

            final_freq_list = np.array(final_freq_list)
            if len(final_freq_list) >= limits.list_maxentries:
                self.log.error('Number of frequency steps too large for microwave device.')
                mode, is_running = self._mw_device.get_status()
                self.sigOutputStateUpdated.emit(mode, is_running)
                return mode, is_running
            freq_list, self.sweep_mw_power, mode = self._mw_device.set_list(final_freq_list,
                                                                            self.sweep_mw_power)

            self.final_freq_list = np.array(freq_list)
            self.mw_starts = used_starts
            self.mw_stops = used_stops
            self.mw_steps = used_steps
            param_dict = {'mw_starts': used_starts, 'mw_stops': used_stops,
                          'mw_steps': used_steps, 'sweep_mw_power': self.sweep_mw_power}

            self.sigParameterUpdated.emit(param_dict)

        elif self.mw_scanmode == MicrowaveMode.SWEEP:
            if self.ranges == 1:
                mw_stop = self.mw_stops[0]
                mw_step = self.mw_steps[0]
                mw_start = self.mw_starts[0]

                if np.abs(mw_stop - mw_start) / mw_step >= limits.sweep_maxentries:
                    self.log.warning('Number of frequency steps too large for microwave device. '
                                     'Lowering resolution to fit the maximum length.')
                    mw_step = np.abs(mw_stop - mw_start) / (limits.list_maxentries - 1)
                    self.sigParameterUpdated.emit({'mw_steps': [mw_step]})

                sweep_return = self._mw_device.set_sweep(
                    mw_start, mw_stop, mw_step, self.sweep_mw_power)
                mw_start, mw_stop, mw_step, self.sweep_mw_power, mode = sweep_return

                param_dict = {'mw_starts': [mw_start], 'mw_stops': [mw_stop],
                              'mw_steps': [mw_step], 'sweep_mw_power': self.sweep_mw_power}
                self.final_freq_list = np.arange(mw_start, mw_stop + mw_step, mw_step)
            else:
                self.log.error('sweep mode only works for one frequency range.')

        else:
            self.log.error('Scanmode not supported. Please select SWEEP or LIST.')

        self.sigParameterUpdated.emit(param_dict)

        if mode != 'list' and mode != 'sweep':
            self.log.error('Switching to list/sweep microwave output mode failed.')
        elif self.mw_scanmode == MicrowaveMode.SWEEP:
            err_code = self._mw_device.sweep_on()
            if err_code < 0:
                self.log.error('Activation of microwave output failed.')
        else:
            err_code = self._mw_device.list_on()
            if err_code < 0:
                self.log.error('Activation of microwave output failed.')

        mode, is_running = self._mw_device.get_status()
        self.sigOutputStateUpdated.emit(mode, is_running)
        return mode, is_running

    def reset_sweep(self):
        """
        Resets the list/sweep mode of the microwave source to the first frequency step.
        """
        if self.mw_scanmode == MicrowaveMode.SWEEP:
            self._mw_device.reset_sweeppos()
        elif self.mw_scanmode == MicrowaveMode.LIST:
            self._mw_device.reset_listpos()
        return

    def mw_off(self):
        """ Switching off the MW source.

        @return str, bool: active mode ['cw', 'list', 'sweep'], is_running
        """
        error_code = self._mw_device.off()
        if error_code < 0:
            self.log.error('Switching off microwave source failed.')

        mode, is_running = self._mw_device.get_status()
        self.sigOutputStateUpdated.emit(mode, is_running)
        return mode, is_running

    def _start_pdmr_counter(self):
        """
        Starting the PDMR counter and set up the clock for it.

        @return int: error code (0:OK, -1:error)
        """

        clock_status = self._pdmr_counter.set_up_pdmr_clock(clock_frequency=self.clock_frequency)
        if clock_status < 0:
            return -1

        counter_status = self._pdmr_counter.set_up_pdmr()
        if counter_status < 0:
            self._pdmr_counter.close_pdmr_clock()
            return -1

        return 0

    def _stop_pdmr_counter(self):
        """
        Stopping the PDMR counter.

        @return int: error code (0:OK, -1:error)
        """

        ret_val1 = self._pdmr_counter.close_pdmr()
        if ret_val1 != 0:
            self.log.error('PDMR counter could not be stopped!')
        ret_val2 = self._pdmr_counter.close_pdmr_clock()
        if ret_val2 != 0:
            self.log.error('PDMR clock could not be stopped!')

        # Check with a bitwise or:
        return ret_val1 | ret_val2

    def start_pdmr_scan(self):
        """ Starting an PDMR scan.

        @return int: error code (0:OK, -1:error)
        """
        with self.threadlock:
            if self.module_state() == 'locked':
                self.log.error('Can not start PDMR scan. Logic is already locked.')
                return -1

            self.set_trigger(self.mw_trigger_pol, self.clock_frequency)

            self.module_state.lock()
            self._clearPdmrData = False
            self.stopRequested = False
            self.fc.clear_result()

            self.elapsed_sweeps = 0
            self.elapsed_time = 0.0
            self._startTime = time.time()
            self.sigPdmrElapsedTimeUpdated.emit(self.elapsed_time, self.elapsed_sweeps)

            pdmr_status = self._start_pdmr_counter()
            if pdmr_status < 0:
                mode, is_running = self._mw_device.get_status()
                self.sigOutputStateUpdated.emit(mode, is_running)
                self.module_state.unlock()
                return -1

            mode, is_running = self.mw_sweep_on()
            if not is_running:
                self._stop_pdmr_counter()
                self.module_state.unlock()
                return -1

            self._initialize_pdmr_plots()
            # initialize raw_data array
            estimated_number_of_lines = self.run_time * self.clock_frequency / self.pdmr_plot_x.size
            estimated_number_of_lines = int(1.5 * estimated_number_of_lines)  # Safety
            if estimated_number_of_lines < self.number_of_lines:
                estimated_number_of_lines = self.number_of_lines
            self.log.debug('Estimated number of raw data lines: {0:d}'
                           ''.format(estimated_number_of_lines))
            self.pdmr_raw_data = np.zeros(
                [estimated_number_of_lines,
                 len(self._pdmr_counter.get_pdmr_channels()),
                 self.pdmr_plot_x.size]
            )
            self.sigNextLine.emit()
            return 0

    def continue_pdmr_scan(self):
        """ Continue PDMR scan.

        @return int: error code (0:OK, -1:error)
        """
        with self.threadlock:
            if self.module_state() == 'locked':
                self.log.error('Can not start PDMR scan. Logic is already locked.')
                return -1

            self.set_trigger(self.mw_trigger_pol, self.clock_frequency)

            self.module_state.lock()
            self.stopRequested = False
            self.fc.clear_result()

            self._startTime = time.time() - self.elapsed_time
            self.sigPdmrElapsedTimeUpdated.emit(self.elapsed_time, self.elapsed_sweeps)

            pdmr_status = self._start_pdmr_counter()
            if pdmr_status < 0:
                mode, is_running = self._mw_device.get_status()
                self.sigOutputStateUpdated.emit(mode, is_running)
                self.module_state.unlock()
                return -1

            mode, is_running = self.mw_sweep_on()
            if not is_running:
                self._stop_pdmr_counter()
                self.module_state.unlock()
                return -1

            self.sigNextLine.emit()
            return 0

    def stop_pdmr_scan(self):
        """ Stop the PDMR scan.

        @return int: error code (0:OK, -1:error)
        """
        with self.threadlock:
            if self.module_state() == 'locked':
                self.stopRequested = True
        return 0

    def clear_pdmr_data(self):
        """¨Set the option to clear the curret PDMR data.

        The clear operation has to be performed within the method
        _scan_pdmr_line. This method just sets the flag for that. """
        with self.threadlock:
            if self.module_state() == 'locked':
                self._clearPdmrData = True
        return

    def _scan_pdmr_line(self):
        """ Scans one line in PDMR

        (from mw_start to mw_stop in steps of mw_step)
        """
        with self.threadlock:
            # If the pdmr measurement is not running do nothing
            if self.module_state() != 'locked':
                return

            # Stop measurement if stop has been requested
            if self.stopRequested:
                self.stopRequested = False
                self.mw_off()
                self._stop_pdmr_counter()
                self.module_state.unlock()
                return

            # if during the scan a clearing of the PDMR data is needed:
            if self._clearPdmrData:
                self.elapsed_sweeps = 0
                self._startTime = time.time()

            # reset position so every line starts from the same frequency
            self.reset_sweep()

            # Acquire count data
            error, new_current = self._pdmr_counter.count_pdmr(length=self.pdmr_plot_x.size)

            if error:
                self.stopRequested = True
                self.sigNextLine.emit()
                return

            # Add new count data to raw_data array and append if array is too small
            if self._clearPdmrData:
                self.pdmr_raw_data[:, :, :] = 0
                self._clearPdmrData = False
            if self.elapsed_sweeps == (self.pdmr_raw_data.shape[0] - 1):
                expanded_array = np.zeros(self.pdmr_raw_data.shape)
                self.pdmr_raw_data = np.concatenate((self.pdmr_raw_data, expanded_array), axis=0)
                self.log.warning('raw data array in PDMRLogic was not big enough for the entire '
                                 'measurement. Array will be expanded.\nOld array shape was '
                                 '({0:d}, {1:d}), new shape is ({2:d}, {3:d}).'
                                 ''.format(self.pdmr_raw_data.shape[0] - self.number_of_lines,
                                           self.pdmr_raw_data.shape[1],
                                           self.pdmr_raw_data.shape[0],
                                           self.pdmr_raw_data.shape[1]))

            # shift data in the array "up" and add new data at the "bottom"
            self.pdmr_raw_data = np.roll(self.pdmr_raw_data, 1, axis=0)

            self.pdmr_raw_data[0] = new_current

            # Add new count data to mean signal
            if self._clearPdmrData:
                self.pdmr_plot_y[:, :] = 0

            if self.lines_to_average <= 0:
                self.pdmr_plot_y = np.mean(
                    self.pdmr_raw_data[:max(1, self.elapsed_sweeps), :, :],
                    axis=0,
                    dtype=np.float64
                )
            else:
                self.pdmr_plot_y = np.mean(
                    self.pdmr_raw_data[:max(1, min(self.lines_to_average, self.elapsed_sweeps)), :, :],
                    axis=0,
                    dtype=np.float64
                )

            # Set plot slice of matrix
            self.pdmr_plot_xy = self.pdmr_raw_data[:self.number_of_lines, :, :]

            # Update elapsed time/sweeps
            self.elapsed_sweeps += 1
            self.elapsed_time = time.time() - self._startTime
            if self.elapsed_time >= self.run_time:
                self.stopRequested = True
            # Fire update signals
            self.sigPdmrElapsedTimeUpdated.emit(self.elapsed_time, self.elapsed_sweeps)
            self.sigPdmrPlotsUpdated.emit(self.pdmr_plot_x, self.pdmr_plot_y, self.pdmr_plot_xy)
            self.sigNextLine.emit()
            return

    def get_pdmr_channels(self):
        return self._pdmr_counter.get_pdmr_channels()

    def get_hw_constraints(self):
        """ Return the names of all ocnfigured fit functions.
        @return object: Hardware constraints object
        """
        constraints = self._mw_device.get_limits()
        return constraints

    def get_fit_functions(self):
        """ Return the hardware constraints/limits
        @return list(str): list of fit function names
        """
        return list(self.fc.fit_list)

    def do_fit(self, fit_function=None, x_data=None, y_data=None, channel_index=0, fit_range=0):
        """
        Execute the currently configured fit on the measurement data. Optionally on passed data
        """
        if (x_data is None) or (y_data is None):
            if fit_range >= 0:
                x_data = self.frequency_lists[fit_range]
                x_data_full_length = np.zeros(len(self.final_freq_list))
                # how to insert the data at the right position?
                start_pos = np.where(np.isclose(self.final_freq_list, self.mw_starts[fit_range]))[0][0]
                x_data_full_length[start_pos:(start_pos + len(x_data))] = x_data
                y_args = np.array([ind_list[0] for ind_list in np.argwhere(x_data_full_length)])
                y_data = self.pdmr_plot_y[channel_index][y_args]
            else:
                x_data = self.final_freq_list
                y_data = self.pdmr_plot_y[channel_index]
        if fit_function is not None and isinstance(fit_function, str):
            if fit_function in self.get_fit_functions():
                self.fc.set_current_fit(fit_function)
            else:
                self.fc.set_current_fit('No Fit')
                if fit_function != 'No Fit':
                    self.log.warning('Fit function "{0}" not available in PDMRLogic fit container.'
                                     ''.format(fit_function))

        self.pdmr_fit_x, self.pdmr_fit_y, result = self.fc.do_fit(x_data, y_data)
        key = 'channel: {0}, range: {1}'.format(channel_index, fit_range)
        if fit_function != 'No Fit':
            self.fits_performed[key] = (self.pdmr_fit_x, self.pdmr_fit_y, result, self.fc.current_fit)
        else:
            if key in self.fits_performed:
                self.fits_performed.pop(key)

        if result is None:
            result_str_dict = {}
        else:
            result_str_dict = result.result_str_dict
        self.sigPdmrFitUpdated.emit(
            self.pdmr_fit_x, self.pdmr_fit_y, result_str_dict, self.fc.current_fit)
        return

    def save_pdmr_data(self, tag=None, colorscale_range=None, percentile_range=None):
        """ Saves the current PDMR data to a file."""
        timestamp = datetime.datetime.now()
        filepath = self._save_logic.get_path_for_module(module_name='PDMR')

        if tag is None:
            tag = ''

        for nch, channel in enumerate(self.get_pdmr_channels()):
            # first save raw data for each channel
            if len(tag) > 0:
                filelabel_raw = '{0}_PDMR_data_ch{1}_raw'.format(tag, nch)
            else:
                filelabel_raw = 'PDMR_data_ch{0}_raw'.format(nch)

            data_raw = OrderedDict()
            data_raw['current data (amps)'] = self.pdmr_raw_data[:self.elapsed_sweeps, nch, :]
            parameters = OrderedDict()
            parameters['Microwave CW Power (dBm)'] = self.cw_mw_power
            parameters['Microwave Sweep Power (dBm)'] = self.sweep_mw_power
            parameters['Run Time (s)'] = self.run_time
            parameters['Number of frequency sweeps (#)'] = self.elapsed_sweeps
            parameters['Start Frequencies (Hz)'] = self.mw_starts
            parameters['Stop Frequencies (Hz)'] = self.mw_stops
            parameters['Step sizes (Hz)'] = self.mw_steps
            parameters['Clock Frequencies (Hz)'] = self.clock_frequency
            parameters['Channel'] = '{0}: {1}'.format(nch, channel)
            self._save_logic.save_data(data_raw,
                                       filepath=filepath,
                                       parameters=parameters,
                                       filelabel=filelabel_raw,
                                       fmt='%.6e',
                                       delimiter='\t',
                                       timestamp=timestamp)

            # now create a plot for each scan range
            data_start_ind = 0
            for ii, frequency_arr in enumerate(self.frequency_lists):
                if len(tag) > 0:
                    filelabel = '{0}_PDMR_data_ch{1}_range{2}'.format(tag, nch, ii)
                else:
                    filelabel = 'PDMR_data_ch{0}_range{1}'.format(nch, ii)

                # prepare the data in a dict or in an OrderedDict:
                data = OrderedDict()
                data['frequency (Hz)'] = frequency_arr

                num_points = len(frequency_arr)
                data_end_ind = data_start_ind + num_points
                data['current data (amps)'] = self.pdmr_plot_y[nch][data_start_ind:data_end_ind]
                data_start_ind += num_points

                parameters = OrderedDict()
                parameters['Microwave CW Power (dBm)'] = self.cw_mw_power
                parameters['Microwave Sweep Power (dBm)'] = self.sweep_mw_power
                parameters['Run Time (s)'] = self.run_time
                parameters['Number of frequency sweeps (#)'] = self.elapsed_sweeps
                parameters['Start Frequency (Hz)'] = frequency_arr[0]
                parameters['Stop Frequency (Hz)'] = frequency_arr[-1]
                parameters['Step size (Hz)'] = frequency_arr[1] - frequency_arr[0]
                parameters['Clock Frequencies (Hz)'] = self.clock_frequency
                parameters['Channel'] = '{0}: {1}'.format(nch, channel)
                parameters['frequency range'] = str(ii)

                key = 'channel: {0}, range: {1}'.format(nch, ii)
                if key in self.fits_performed.keys():
                    parameters['Fit function'] = self.fits_performed[key][3]
                    for name, param in self.fits_performed[key][2].params.items():
                        parameters[name] = str(param)
                # add all fit parameter to the saved data:

                fig = self.draw_figure(nch, ii,
                                       cbar_range=colorscale_range,
                                       percentile_range=percentile_range)

                self._save_logic.save_data(data,
                                           filepath=filepath,
                                           parameters=parameters,
                                           filelabel=filelabel,
                                           fmt='%.6e',
                                           delimiter='\t',
                                           timestamp=timestamp,
                                           plotfig=fig)

        self.log.info('PDMR data saved to:\n{0}'.format(filepath))
        return

    def draw_figure(self, channel_number, freq_range, cbar_range=None, percentile_range=None):
        """ Draw the summary figure to save with the data.

        @param: list cbar_range: (optional) [color_scale_min, color_scale_max].
                                 If not supplied then a default of data_min to data_max
                                 will be used.

        @param: list percentile_range: (optional) Percentile range of the chosen cbar_range.

        @return: fig fig: a matplotlib figure object to be saved to file.
        """
        key = 'channel: {0}, range: {1}'.format(channel_number, freq_range)
        freq_data = self.frequency_lists[freq_range]
        lengths = [len(freq_range) for freq_range in self.frequency_lists]
        cumulative_sum = list()
        tmp_val = 0
        cumulative_sum.append(tmp_val)
        for length in lengths:
            tmp_val += length
            cumulative_sum.append(tmp_val)

        ind_start = cumulative_sum[freq_range]
        ind_end = cumulative_sum[freq_range + 1]
        current_data = self.pdmr_plot_y[channel_number][ind_start:ind_end]
        fit_freq_vals = self.frequency_lists[freq_range]
        if key in self.fits_performed:
            fit_count_vals = self.fits_performed[key][2].eval()
        else:
            fit_count_vals = 0.0
        matrix_data = self.select_pdmr_matrix_data(self.pdmr_plot_xy, channel_number, freq_range)

        # If no colorbar range was given, take full range of data
        if cbar_range is None:
            cbar_range = np.array([np.min(matrix_data), np.max(matrix_data)])
        else:
            cbar_range = np.array(cbar_range)

        prefix = ['', 'k', 'M', 'G', 'T']
        prefix_index = 0

        # Rescale counts data with SI prefix
        while np.max(current_data) > 1000:
            current_data = current_data / 1000
            fit_count_vals = fit_count_vals / 1000
            prefix_index = prefix_index + 1

        counts_prefix = prefix[prefix_index]

        # Rescale frequency data with SI prefix
        prefix_index = 0

        while np.max(freq_data) > 1000:
            freq_data = freq_data / 1000
            fit_freq_vals = fit_freq_vals / 1000
            prefix_index = prefix_index + 1

        mw_prefix = prefix[prefix_index]

        # Rescale matrix counts data with SI prefix
        prefix_index = 0

        while np.max(matrix_data) > 1000:
            matrix_data = matrix_data / 1000
            cbar_range = cbar_range / 1000
            prefix_index = prefix_index + 1

        cbar_prefix = prefix[prefix_index]

        # Use qudi style
        plt.style.use(self._save_logic.mpl_qd_style)

        # Create figure
        fig, (ax_mean, ax_matrix) = plt.subplots(nrows=2, ncols=1)

        ax_mean.plot(freq_data, current_data, linestyle=':', linewidth=0.5)

        # Do not include fit curve if there is no fit calculated.
        if hasattr(fit_count_vals, '__len__'):
            ax_mean.plot(fit_freq_vals, fit_count_vals, marker='None')

        ax_mean.set_ylabel('Current (' + counts_prefix + 'A)')
        ax_mean.set_xlim(np.min(freq_data), np.max(freq_data))

        matrixplot = ax_matrix.imshow(
            matrix_data,
            cmap=plt.get_cmap('inferno'),  # reference the right place in qd
            origin='lower',
            vmin=cbar_range[0],
            vmax=cbar_range[1],
            extent=[np.min(freq_data),
                    np.max(freq_data),
                    0,
                    self.number_of_lines
                    ],
            aspect='auto',
            interpolation='nearest')

        ax_matrix.set_xlabel('Frequency (' + mw_prefix + 'Hz)')
        ax_matrix.set_ylabel('Scan #')

        # Adjust subplots to make room for colorbar
        fig.subplots_adjust(right=0.8)

        # Add colorbar axis to figure
        cbar_ax = fig.add_axes([0.85, 0.15, 0.02, 0.7])

        # Draw colorbar
        cbar = fig.colorbar(matrixplot, cax=cbar_ax)
        cbar.set_label('Fluorescence (' + cbar_prefix + 'c/s)')

        # remove ticks from colorbar for cleaner image
        cbar.ax.tick_params(which=u'both', length=0)

        # If we have percentile information, draw that to the figure
        if percentile_range is not None:
            cbar.ax.annotate(str(percentile_range[0]),
                             xy=(-0.3, 0.0),
                             xycoords='axes fraction',
                             horizontalalignment='right',
                             verticalalignment='center',
                             rotation=90
                             )
            cbar.ax.annotate(str(percentile_range[1]),
                             xy=(-0.3, 1.0),
                             xycoords='axes fraction',
                             horizontalalignment='right',
                             verticalalignment='center',
                             rotation=90
                             )
            cbar.ax.annotate('(percentile)',
                             xy=(-0.3, 0.5),
                             xycoords='axes fraction',
                             horizontalalignment='right',
                             verticalalignment='center',
                             rotation=90
                             )

        return fig

    def select_pdmr_matrix_data(self, pdmr_matrix, nch, freq_range):
        pdmr_matrix_dp = pdmr_matrix[:, nch]
        x_data = self.frequency_lists[freq_range]
        x_data_full_length = np.zeros(len(self.final_freq_list))
        mw_starts = [freq_arr[0] for freq_arr in self.frequency_lists]
        start_pos = np.where(np.isclose(self.final_freq_list,
                                        mw_starts[freq_range]))[0][0]
        x_data_full_length[start_pos:(start_pos + len(x_data))] = x_data
        y_args = np.array([ind_list[0] for ind_list in np.argwhere(x_data_full_length)])
        pdmr_matrix_range = pdmr_matrix_dp[:, y_args]
        return pdmr_matrix_range

    def perform_pdmr_measurement(self, freq_start, freq_step, freq_stop, power, channel, runtime,
                                 fit_function='No Fit', save_after_meas=True, name_tag=''):
        """ An independant method, which can be called by a task with the proper input values
            to perform an pdmr measurement.

        @return
        """
        timeout = 30
        start_time = time.time()
        while self.module_state() != 'idle':
            time.sleep(0.5)
            timeout -= (time.time() - start_time)
            if timeout <= 0:
                self.log.error('perform_pdmr_measurement failed. Logic module was still locked '
                               'and 30 sec timeout has been reached.')
                return tuple()

        # set all relevant parameter:
        self.set_sweep_parameters(freq_start, freq_stop, freq_step, power)
        self.set_runtime(runtime)

        # start the scan
        self.start_pdmr_scan()

        # wait until the scan has started
        while self.module_state() != 'locked':
            time.sleep(1)
        # wait until the scan has finished
        while self.module_state() == 'locked':
            time.sleep(1)

        # Perform fit if requested
        if fit_function != 'No Fit':
            self.do_fit(fit_function, channel_index=channel)
            fit_params = self.fc.current_fit_param
        else:
            fit_params = None

        # Save data if requested
        if save_after_meas:
            self.save_pdmr_data(tag=name_tag)

        return self.pdmr_plot_x, self.pdmr_plot_y, fit_params

# -*- coding: utf-8 -*-
"""
This file contains a Qudi logic module for sweeping a tunable laser
and measuring count rates, typically employed for PLE experiments.

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

from collections import OrderedDict
import datetime
import matplotlib.pyplot as plt
import numpy as np
import time

from core.module import Connector, StatusVar
from core.util.mutex import Mutex
from logic.generic_logic import GenericLogic
from qtpy import QtCore


class PLELogic(GenericLogic):

    """This logic module controls scans of laser frequency for tunable lasers.
    It collects countrate as a function of laser frequency.
    """

    sig_data_updated = QtCore.Signal()

    _modclass = 'plelogic'
    _modtype = 'logic'

    # declare connectors
    slowcounter = Connector(interface='CounterLogic')
    tunablelaserlogic = Connector(interface='TunableLaserLogic')
    savelogic = Connector(interface='SaveLogic')

    scan_range = StatusVar('scan_range', [-10, 10])
    number_of_repeats = StatusVar(default=10)
    resolution = StatusVar('resolution', 500)
    _switch_delay = StatusVar('switch_delay', 0.5)
    _settling_time = StatusVar('settling_time', 1)
    _integration_time = StatusVar('integration_time', 0.3)

    sigChangePosition = QtCore.Signal(float)
    sigWavelengthChanged = QtCore.Signal(float)
    sigScanNextLine = QtCore.Signal()
    sigUpdatePlots = QtCore.Signal()
    sigScanFinished = QtCore.Signal()
    sigScanStarted = QtCore.Signal()

    def __init__(self, **kwargs):
        """ Create VoltageScanningLogic object with connectors.

          @param dict kwargs: optional parameters
        """
        super().__init__(**kwargs)

        # locking for thread safety
        self.threadlock = Mutex()
        self.stopRequested = False

        self.fit_x = []
        self.fit_y = []
        self.plot_x = []
        self.plot_y = []
        self.plot_y2 = []

    def on_activate(self):
        """ Initialisation performed during activation of the module.
        """
        self._counter = self.slowcounter()
        self._tunable_laser = self.tunablelaserlogic()
        self._save_logic = self.savelogic()

        # initialize the wavelength controls based on current laser control scheme
        self.update_wavelength_controls()

        # Sets connections between signals and functions
#        self.sigChangePosition.connect(self._change_position, QtCore.Qt.QueuedConnection)
        self.sigScanNextLine.connect(self._do_next_line, QtCore.Qt.QueuedConnection)

        # Initialization of internal counter for scanning
        self._scan_counter_up = 0
        self._scan_counter_down = 0
        # Keep track of scan direction
        self.upwards_scan = True

        # calculated number of points in a scan, depends on speed and max step size
        self._num_of_steps = 50  # initialising.  This is calculated for a given ramp.

        # default values for clock frequency and slowness
        # slowness: steps during retrace line
        self.set_resolution(self.resolution)
        self.set_integration_time(self._integration_time)
        self.set_settling_time(self._settling_time)

        # Initialize data matrix
        self._initialise_data_matrix(100)

        # Connect to the signal which tells us that the laser control scheme
        # has been modified
        self._tunable_laser.sigWavelengthControlModeChanged.connect(self.update_wavelength_controls)

    def update_wavelength_controls(self):
        """ Called when the control scheme of the laser wavelength is changed to / from
        VOLTAGE and WAVELENGTH. Will cause problems if the scheme is changed mid-scan """
        # Reads in the maximal tuning range. The unit of the scan range
        # depends on the laser - voltage or wavelength
        self.scan_limits = self._tunable_laser.laser_wavelength_range

        # initialise the range for scanning
        self.set_scan_range(self.scan_limits)

        # ensure position has been updated since changing control scheme
        time.sleep(0.05)

        # keep track of where we currently are
        self._static_position = self._tunable_laser.laser_wavelength_setpoint

    def on_deactivate(self):
        """ Deinitialisation performed during deactivation of the module.
        """
        self.stopRequested = True

    def set_resolution(self, resolution):
        """ Calculate clock rate from scan speed and desired number of pixels """
        self.resolution = int(resolution)
        return 0

    def set_scan_range(self, scan_range):
        """ Set the scan range """
        r_max = np.clip(scan_range[1], self.scan_limits[0], self.scan_limits[1])
        r_min = np.clip(scan_range[0], self.scan_limits[0], r_max)
        self.scan_range = [r_min, r_max]

    def set_position(self, position):
        """ Set the channel idle voltage """
        self._static_position = np.clip(position, self.scan_limits[0], self.scan_limits[1])

    def set_integration_time(self, integration_time):
        """ Set integration time in seconds for each point """
        self._integration_time_bins = int(np.floor(integration_time/self._counter.get_count_frequency()))
        self._integration_time = integration_time

    def set_settling_time(self, settling_time):
        """ Set the settling time for the laser before accumulating counts """
        self._settling_time = settling_time

    def set_switch_delay(self, switch_delay):
        """ Set the delay time for the laser to switch frequency between each point in a scan
        before accumulating counts """
        self._switch_delay = switch_delay

    def set_scan_lines(self, scan_lines):
        self.number_of_repeats = int(np.clip(scan_lines, 1, 1e6))

    def _initialise_data_matrix(self, scan_length):
        """ Initializing the PLE matrix plot. """

        self.scan_matrix = np.zeros((self.number_of_repeats, scan_length))
        self.scan_matrix2 = np.zeros((self.number_of_repeats, scan_length))
        self.plot_x = np.linspace(self.scan_range[0], self.scan_range[1], scan_length)
        self.plot_y = np.zeros(scan_length)
        self.plot_y2 = np.zeros(scan_length)
        self.fit_x = np.linspace(self.scan_range[0], self.scan_range[1], scan_length)
        self.fit_y = np.zeros(scan_length)

    def get_current_position(self):
        """Get current tunable laser position

        @return float: Current tunable laser position in units defined by the laser"""
        return self._tunable_laser.laser_wavelength_setpoint

    @QtCore.Slot(float)
    def set_wavelength(self, wavelength):
        """ Set the wavelength """
        self._tunable_laser.set_wavelength(wavelength)
        self.sigWavelengthChanged.emit(wavelength)

    def _initialise_scanner(self):
        """Initialise the clock and locks for a scan"""
        self.module_state.lock()
        return 0

    def start_scanning(self):
        """Setting up the scanner device and starts the scanning procedure

        @return int: error code (0:OK, -1:error)
        """
        self._static_position = self._tunable_laser.laser_wavelength_setpoint
        print(self._static_position)

        self._scan_counter_up = 0
        self._scan_counter_down = 0
        self.upwards_scan = True

        # TODO: Generate Ramps
        self._initialise_data_matrix(self.resolution)

        # Lock and set up scanner
        returnvalue = self._initialise_scanner()
        if returnvalue < 0:
            # TODO: error message
            return -1

        self.sigScanNextLine.emit()
        self.sigScanStarted.emit()
        return 0

    def stop_scanning(self):
        """Stops the scan

        @return int: error code (0:OK, -1:error)
        """
        with self.threadlock:
            if self.module_state() == 'locked':
                self.stopRequested = True
        return 0

    def _close_scanner(self):
        """Close the scanner and unlock"""
        with self.threadlock:
            self.stopRequested = False
            if self.module_state.can('unlock'):
                self.module_state.unlock()

    def _do_next_line(self):
        """ If stopRequested then finish the scan, otherwise perform next repeat of the scan line
        """
        # stops scanning
        if self.stopRequested or self._scan_counter_down >= self.number_of_repeats:
            self._tunable_laser.set_wavelength(self._static_position)
            self._close_scanner()
            self.sigScanFinished.emit()
            return

        # this is called before the first scan
        if self._scan_counter_up == 0:
            # move from current position to start of scan range.
            wavelength = self.scan_range[0]
            self._tunable_laser.set_wavelength(wavelength)
            time.sleep(self._settling_time)

        # self.scan_matrix[self._scan_counter_up,:] = counts
        # self.plot_y += counts
        # self._scan_counter_up += 1
        # perform next scan - down or up depending on value of "upwards scan"
        counts = self._scan_line(self.upwards_scan)
        if self.upwards_scan:
            self.scan_matrix[self._scan_counter_up,:] = counts
            self.plot_y += counts
            self._scan_counter_up += 1
            self.upwards_scan = False
        else:
            self.scan_matrix2[self._scan_counter_down,:] = np.flip(counts, 0)
            self.plot_y2 += counts
            self._scan_counter_down += 1
            self.upwards_scan = True

        self.sigUpdatePlots.emit()
        self.sigScanNextLine.emit()

    # TODO
    def _scan_line(self, scan_upwards):
        """ Perform a single frequency scan and record APD counts """
        try:
            if scan_upwards:
                wavelength = self.scan_range[0]
                step_size = (self.scan_range[1] - self.scan_range[0]) / (self.resolution - 1)
            else:
                wavelength = self.scan_range[1]
                step_size = -(self.scan_range[1] - self.scan_range[0]) / (self.resolution - 1)

            count_data = np.zeros(self.resolution)

            for i in range(self.resolution):
                self._tunable_laser.set_wavelength(wavelength)
                time.sleep(self._switch_delay)
                time.sleep(self._integration_time)

                point_counts = self._counter.countdata[0, -self._integration_time_bins:]
                count_data[i] = np.mean(point_counts)
                wavelength += step_size

            return np.array(count_data)

        except Exception as e:
            self.log.error('The scan went wrong, killing the scanner.')
            self.stop_scanning()
            self.sigScanNextLine.emit()
            raise e

    # TODO
    def save_data(self, tag=None, colorscale_range=None, percentile_range=None):
        """ Save the counter trace data and writes it to a file.

        @return int: error code (0:OK, -1:error)
        """
        if tag is None:
            tag = ''

        self._saving_stop_time = time.time()

        filepath = self._save_logic.get_path_for_module(module_name='LaserScanning')
        filepath2 = self._save_logic.get_path_for_module(module_name='LaserScanning')
        filepath3 = self._save_logic.get_path_for_module(module_name='LaserScanning')
        timestamp = datetime.datetime.now()

        if len(tag) > 0:
            filelabel = tag + '_volt_data'
            filelabel2 = tag + '_volt_data_raw_trace'
            filelabel3 = tag + '_volt_data_raw_retrace'
        else:
            filelabel = 'volt_data'
            filelabel2 = 'volt_data_raw_trace'
            filelabel3 = 'volt_data_raw_retrace'

        # prepare the data in a dict or in an OrderedDict:
        data = OrderedDict()
        data['frequency (Hz)'] = self.plot_x
        data['trace count data (counts/s)'] = self.plot_y
        data['retrace count data (counts/s)'] = self.plot_y2

        data2 = OrderedDict()
        data2['count data (counts/s)'] = self.scan_matrix[:self._scan_counter_up, :]

        data3 = OrderedDict()
        data3['count data (counts/s)'] = self.scan_matrix2[:self._scan_counter_down, :]

        parameters = OrderedDict()
        parameters['Number of frequency sweeps (#)'] = self._scan_counter_up
        parameters['Start Voltage (V)'] = self.scan_range[0]
        parameters['Stop Voltage (V)'] = self.scan_range[1]
        parameters['Scan speed [V/s]'] = self._scan_speed
        parameters['Clock Frequency (Hz)'] = self._clock_frequency

        fig = self.draw_figure(
            self.scan_matrix,
            self.plot_x,
            self.plot_y,
            self.fit_x,
            self.fit_y,
            cbar_range=colorscale_range,
            percentile_range=percentile_range)

        fig2 = self.draw_figure(
            self.scan_matrix2,
            self.plot_x,
            self.plot_y2,
            self.fit_x,
            self.fit_y,
            cbar_range=colorscale_range,
            percentile_range=percentile_range)

        self._save_logic.save_data(
            data,
            filepath=filepath,
            parameters=parameters,
            filelabel=filelabel,
            fmt='%.6e',
            delimiter='\t',
            timestamp=timestamp
        )

        self._save_logic.save_data(
            data2,
            filepath=filepath2,
            parameters=parameters,
            filelabel=filelabel2,
            fmt='%.6e',
            delimiter='\t',
            timestamp=timestamp,
            plotfig=fig
        )

        self._save_logic.save_data(
            data3,
            filepath=filepath3,
            parameters=parameters,
            filelabel=filelabel3,
            fmt='%.6e',
            delimiter='\t',
            timestamp=timestamp,
            plotfig=fig2
        )

        self.log.info('Laser Scan saved to:\n{0}'.format(filepath))
        return 0

    # TODO
    def draw_figure(self, matrix_data, freq_data, count_data, fit_freq_vals, fit_count_vals, cbar_range=None, percentile_range=None):
        """ Draw the summary figure to save with the data.

        @param: list cbar_range: (optional) [color_scale_min, color_scale_max].
                                 If not supplied then a default of data_min to data_max
                                 will be used.

        @param: list percentile_range: (optional) Percentile range of the chosen cbar_range.

        @return: fig fig: a matplotlib figure object to be saved to file.
        """

        # If no colorbar range was given, take full range of data
        if cbar_range is None:
            cbar_range = np.array([np.min(matrix_data), np.max(matrix_data)])
        else:
            cbar_range = np.array(cbar_range)

        prefix = ['', 'k', 'M', 'G', 'T']
        prefix_index = 0

        # Rescale counts data with SI prefix
        while np.max(count_data) > 1000:
            count_data = count_data / 1000
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

        ax_mean.plot(freq_data, count_data, linestyle=':', linewidth=0.5)

        # Do not include fit curve if there is no fit calculated.
        if max(fit_count_vals) > 0:
            ax_mean.plot(fit_freq_vals, fit_count_vals, marker='None')

        ax_mean.set_ylabel('Fluorescence (' + counts_prefix + 'c/s)')
        ax_mean.set_xlim(np.min(freq_data), np.max(freq_data))

        matrixplot = ax_matrix.imshow(
            matrix_data,
            cmap=plt.get_cmap('inferno'),  # reference the right place in qd
            origin='lower',
            vmin=cbar_range[0],
            vmax=cbar_range[1],
            extent=[
                np.min(freq_data),
                np.max(freq_data),
                0,
                self.number_of_repeats
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
        cbar.ax.tick_params(which='both', length=0)

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

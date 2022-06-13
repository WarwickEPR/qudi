# -*- coding: utf-8 -*-

"""
This module contains the Qudi interface file for an "other" single voltage scanner.

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
from core.module import Base
from interface.voltage_scanner_interface import VoltageScannerInterface

class AOMScannerDummy(Base, VoltageScannerInterface):
    """ Dummy hardware for performing AOM power scans (psat)
    """

    def on_activate(self):
        self._voltage = 0

    def on_deactivate(self):
        pass

    def set_voltage(self, v):
        """Set output to voltage v.

        @param float v: (volts)

        @return int: error code (0:OK, -1:error)
        """
        self._voltage = v
        return 0

    def get_voltage(self):
        """ Get the current voltage.

        @return float: current voltage in  volts.
        """
        return self._voltage

    def scan_voltage(self, voltages=None, pixel_clock=False):
        """ Scans the voltage and returns the counts at each point.

        @param float[k] line_path: array k defining the voltages

        @return float[k]: the photon counts per second for each point
        """
        voltages = np.linspace(0, np.max(voltages), np.size(voltages))
        def psat(V):
            return 100000 * np.random.normal(loc=1, scale=0.05) * V / (V + 0.1 * np.max(voltages)) 
        return np.multiply(np.random.normal(loc=1, scale=0.03, size=np.shape(voltages)), psat(voltages))

    # needed for compatibility with the aom logic, which assumes you're using an NI card
    def set_up_scanner_clock(self, **kwargs):
        pass

    def set_up_scanner(self):
        pass

    def close_scanner(self):
        pass

    def close_scanner_clock(self):
        pass
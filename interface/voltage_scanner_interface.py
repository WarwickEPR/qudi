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

import abc
from core.util.interfaces import InterfaceMetaclass

class VoltageScannerInterface(metaclass=InterfaceMetaclass):
    """ This is the Interface class to define the controls for generic voltage sweeping hardware.
    """

    _modtype = 'VoltageScannerInterface'
    _modclass = 'interface'

    @abc.abstractmethod
    def set_voltage(self, v):
        """Set output to voltage v.

        @param float v: (volts)

        @return int: error code (0:OK, -1:error)
        """
        pass

    @abc.abstractmethod
    def get_voltage(self):
        """ Get the current voltage.

        @return float: current voltage in  volts.
        """
        pass

    @abc.abstractmethod
    def scan_voltage(self, voltages=None, pixel_clock=False):
        """ Scans the voltage and returns the counts at each point.

        @param float[k] line_path: array k defining the voltages

        @return float[k]: the photon counts per second for each point
        """
        pass


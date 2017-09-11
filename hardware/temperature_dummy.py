# -*- coding: utf-8 -*-
"""
Dummy implementation for process control.

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

from core.module import Base, ConfigOption
from interface.process_interface import ProcessInterface


class TemperatureDummy(Base, ProcessInterface):
    """ Reports the configured temperature without measurement.
    """
    _modclass = 'temperature_dummy'
    _modtype = 'hardware'

    _temperature = ConfigOption('temperature', missing='error')

    def on_activate(self):
        """ Activate module.
        """
        pass

    def on_deactivate(self):
        """ Deactivate module.
        """
        pass

    def getProcessValue(self):
        """ Process value, here temperature.

            @return float: temperature
        """
        return self._temperature

    def getProcessUnit(self):
        """ Process unit, here kelvin.

            @return float: temperature unit
        """
        return 'K', 'kelvin'

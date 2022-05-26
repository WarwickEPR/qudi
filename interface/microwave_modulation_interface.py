# -*- coding: utf-8 -*-

"""
This file contains an extended Qudi Interface file to control modulation
options on microwave devices such as I/Q modulation inputs.

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

from core.interface import abstract_interface_method
from core.meta import InterfaceMetaclass
from core.util.helpers import in_range
from enum import Enum

from interface.microwave_interface import MicrowaveInterface


class MicrowaveModulationInterface(MicrowaveInterface):
    """This is the Interface class to define the controls for the microwave hardware with modulation capabilities.

    This augments the basic microwave configuration options to also support configuration of modulation
    """

    @abstract_interface_method
    def turn_on_external_iq_modulation(self):
        """ Configure and turn on IQ modulation.

        @return float: the magnitude of the voltage applied to external I/Q modulation inputs
        """
        pass

    @abstract_interface_method
    def turn_off_external_iq_modulation(self):
        """ Deconfigure and turn off I/Q modulation.

        @return float: the magnitude of the voltage applied to external I/Q modulation inputs
        """
        pass

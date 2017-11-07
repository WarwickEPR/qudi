# -*- coding: utf-8 -*-

"""
This file contains the Qudi Logic module for scanning the Attocube z

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

from qtpy import QtCore
from collections import OrderedDict
from interface.microwave_interface import MicrowaveMode
from interface.microwave_interface import TriggerEdge
import numpy as np
import time
import datetime
import matplotlib.pyplot as plt
import lmfit

from logic.generic_logic import GenericLogic
from core.util.mutex import Mutex
from core.module import Connector, ConfigOption, StatusVar

class AttocubeZScanLogic(GenericLogic):

    """This is the Logic class for taking short-range (<1um) focusing scans using
       the Attocube stepper stage's offset as an improvised piezo scanner."""
    _modclass = 'attocube_z_scan_logic'
    _modtype = 'logic'

    # declare connectors
    stepper = Connector(interface='PiezoStepperInterface')
    gated_counter = Connector(interface='GatedCounterInterface')

    _offset_list = ConfigOption('offset_list', 'quick', missing='error')
    _dwell = ConfigOption('dwell', 50, missing='warn')

    #fitlogic = Connector(interface='FitLogic')
    #savelogic = Connector(interface='SaveLogic')

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)

        self.offsets = np.zeros(0)
        self.rates = np.zeros(0)
        self.dwell = 50
        self.offset_list = ''

    def _offsets(self, offset_list):
        return np.array(self._stepper.get_offset_list(offset_list))

    def on_activate(self):
        """
        Initialisation performed during activation of the module.
        """
        # Get connectors
        self._stepper = self.get_connector('stepper')
        self._counter = self.get_connector('gated_counter')

        config = self.getConfiguration()
        self.offset_list = config['offset_list']
        self.dwell = config['dwell']
        self.offsets = np.array(self._stepper.get_offset_list(self.offset_list))
        self.rates = np.zeros_like(self.offsets)

        self._counter.configure_gated_counter('z', len(self.offsets)+1, 'both', 'z')

        return

    def on_deactivate(self):
        """ Deinitialisation performed during deactivation of the module.
        """
        self._counter.stop_gated_counter('z')  # just in case

    def scan_z(self):
        """ Scan the stepper stage and record count rates """
        self._counter.start_gated_counter('z')
        self._stepper.scan_offset('z', self.offset_list, self.dwell)
        time.sleep(self.dwell/1000*len(self.offsets)*1.7)  # guess how long
        for i in range(10):  # won't take long
            self.rates = self._counter.get_rates_gated_counter('z')
            # self.log.info("Rates: {}".format(self.rates))
            if len(self.rates) >= len(self.offsets):
                break
            else:
                time.sleep(self.dwell/1000*2)
        self.rates.resize(len(self.offsets))
        self._counter.stop_gated_counter('z')

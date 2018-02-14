"""
This module performs an HBT and saves data appropriately

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
import numpy as np
from logic.generic_logic import GenericLogic
from core.module import Connector, ConfigOption
import TimeTagger as tt

class HbtLogic(GenericLogic):
    """
    This is the logic for running HBT experiments
    """
    _modclass = 'hbtlogic'
    _modtype = 'logic'

    _channel_apd_0 = ConfigOption('timetagger_channel_apd_0', missing='error')
    _channel_apd_1 = ConfigOption('timetagger_channel_apd_1', missing='error')
    _bin_width = ConfigOption('bin_width', 500, missing='info')
    _n_bins = ConfigOption('bins', 2000, missing='info')

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)
        self.data = []

    def on_activate(self):
        """ Connect and configure the access to the FPGA.
        """
        self._save_logic = Connector(interface='savelogic')
        self._tagger = tt.createTimeTagger()
        self._number_of_gates = int(100)
        self.coin = tt.Correlation(self._tagger, self._channel_apd_0, self._channel_apd_1,
                                   binwidth=self._bin_width, n_bins=self._n_bins)
        # start the correlation (iterate start stop just to clear last if not a fresh reload)
        self.coin.stop()
        self.coin.clear()

    def start_hbt(self):
        self.coin.clear()
        self.coin.start()

    def update(self):
        self.data = self.coin.getData()

    def pause_hbt(self):
        self.coin.stop()

    def continue_hbt(self):
        self.coin.start()

    def stop_hbt(self):
        self.coin.stop()

    def fit_data(self):
        pass
        # model, param = self.fitlogic.make_hyperbolicsaturation_model()
        # param['I_sat'].min = 0
        # param['I_sat'].max = 1e7
        # param['I_sat'].value = max(self.psat_data) * .7
        # param['P_sat'].max = 100.0
        # param['P_sat'].min = 0.0
        # param['P_sat'].value = 1.0
        # param['slope'].min = 0.0
        # param['slope'].value = 1e3
        # param['offset'].min = 0.0
        # fit = self.fitlogic.make_hyperbolicsaturation_fit(x_axis=self.psat_powers, data=self.psat_data,
        #                                                   estimator=self.fitlogic.estimate_hyperbolicsaturation,
        #                                                   add_params=param)
        # self.fit = fit
        # self.fitted_Psat = fit.best_values['P_sat']
        # self.fitted_Isat = fit.best_values['I_sat']

    def save_hbt(self):
        # File path and name
        filepath = self._save_logic.get_path_for_module(module_name='HBT')

        # We will fill the data OrderedDict to send to savelogic
        data = OrderedDict()
        data['Time (ns)'] = np.array(self.data)
        data['g2(t)'] = np.array(self.data)

        self._save_logic.save_data(data, filepath=filepath, filelabel='g2data', fmt=['%.6e', '%.6e'])
        self.log.debug('HBT data saved to:\n{0}'.format(filepath))

        return 0

    def on_deactivate(self):
        """ Reverse steps of activation

        @return int: error code (0:OK, -1:error)
        """
        return 0
# -*- coding: utf-8 -*-

"""
This file contains the Qudi HBT gui.

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
import os
import pyqtgraph as pg

from core.module import Connector
from gui.colordefs import QudiPalettePale as palette
from gui.guibase import GUIBase
from qtpy import QtCore
from qtpy import QtWidgets
from qtpy import uic



class HbtMainWindow(QtWidgets.QMainWindow):

    """ Create the Main Window based on the *.ui file. """

    def __init__(self, **kwargs):
        # Get the path to the *.ui file
        this_dir = os.path.dirname(__file__)
        ui_file = os.path.join(this_dir, 'ui_hbt.ui')

        # Load it
        super().__init__(**kwargs)
        uic.loadUi(ui_file, self)
        self.show()


class HbtGui(GUIBase):

    """ FIXME: Please document
    """
    _modclass = 'hbtgui'
    _modtype = 'gui'

    # declare connectors
    hbtlogic = Connector(interface='HbtLogic')

    sigHbtStopped = QtCore.Signal()
    sigHbtFitted = QtCore.Signal()

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)

    def on_activate(self):
        """ Definition and initialisation of the GUI.
        """

        self._hbt_logic = self.get_connector('hbtlogic')

        # Use the inherited class 'CounterMainWindow' to create the GUI window
        self._mw = HbtMainWindow()

        self.hbt_image = pg.PlotDataItem(self._hbt_logic.bin_times/1000,
                                         self._hbt_logic.g2_data_normalised,
                                         pen=None,
                                         symbol='o',
                                         symbolPen=palette.c1,
                                         symbolBrush=palette.c1,
                                         symbolSize=3)

        self.hbt_fit_image = pg.PlotDataItem(self._hbt_logic.fit_times,
                                             self._hbt_logic.fit_g2,
                                             pen=pg.mkPen(palette.c2))

        # Add the display item to the xy and xz ViewWidget, which was defined in the UI file.
        self._mw.hbt_plot_PlotWidget.addItem(self.hbt_image)
        #self._mw.psat_plot_PlotWidget.addItem(self.hbt_fit_image)
        self._mw.hbt_plot_PlotWidget.setLabel(axis='left', text='g2(t)', units='normalised units')
        self._mw.hbt_plot_PlotWidget.setLabel(axis='bottom', text='Time', units='ns')
        self._mw.hbt_plot_PlotWidget.showGrid(x=True, y=True, alpha=0.8)

        #####################
        # Connecting user interactions
        self._mw.run_hbt_Action.toggled.connect(self.run_hbt_toggled)
        self._mw.save_hbt_Action.triggered.connect(self.save_clicked)

        ##################
        # Handling signals from the logic
        self._hbt_logic.hbt_updated.connect(self.update_data)
        self._hbt_logic.hbt_fit_updated.connect(self.update_fit)

        return 0

    def run_hbt_toggled(self, run):
        if run:
            self._hbt_logic.start_hbt()
        else:
            self._hbt_logic.stop_hbt()

    def show(self):
        """Make window visible and put it above all other windows.
        """
        QtWidgets.QMainWindow.show(self._mw)
        self._mw.activateWindow()
        self._mw.raise_()
        return

    def on_deactivate(self):
        """ Deactivate the module
        """
        # disconnect signals
        self._mw.close()
        return

    def update_data(self):
        """ The function that grabs the data and sends it to the plot.
        """

        """ Refresh the plot widgets with new data. """
        # Update psat plot
        self.hbt_image.setData(self._hbt_logic.bin_times/1000, self._hbt_logic.g2_data_normalised)

        return 0

    def update_fit(self):
        """ Refresh the plot widgets with new data. """
        if self._hbt_logic.hbt_fit_available():
            # Update hbt plot
            self.hbt_fit_image.setData(self._hbt_logic.hbt_fit_x, self._hbt_logic.hbt_fit_y)

    def save_clicked(self):
        """ Handling the save button to save the data into a file.
        """
        if self._hbt_logic.hbt_available:
            self._hbt_logic.save_hbt()

import os
import pyqtgraph as pg
import time

from core.connector import Connector
from core.configoption import ConfigOption
from core.statusvariable import StatusVar
from gui.colordefs import QudiPalettePale as palette
from gui.guibase import GUIBase
from qtpy import QtCore
from qtpy import QtWidgets
from qtpy import uic
from interface.data_instream_interface import StreamChannelType



class PicoAmmeterGUIMainWindow(QtWidgets.QMainWindow):
    def __init__(self, **kwargs):
        this_dir = os.path.dirname(__file__)
        ui_file = os.path.join(this_dir, 'ui_picoammeter_gui.ui')

        super().__init__(**kwargs)
        uic.loadUi(ui_file, self)
        self.show()


class PicoAmmeterGUI(GUIBase):
    # declare ConfigOptions
    _use_antialias = ConfigOption('use_antialias', default=True)

    # declare connectors
    picoammeterlogic = Connector(interface='PicoAmmeterLogic')

    sigStartCounter = QtCore.Signal()
    sigStopCounter = QtCore.Signal()
    sigStartRecording = QtCore.Signal()
    sigStopRecording = QtCore.Signal()
    sigVoltage = QtCore.Signal(bool)
    sigVRangeChange = QtCore.Signal(int)
    sigCRangeChange = QtCore.Signal(int)
    sigVValueChange = QtCore.Signal(bool)


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._mw = None
        self._pw = None



        return

    def on_activate(self):
        self._picoammeter_logic = self.picoammeterlogic()


        self._use_antialias = bool(self._use_antialias)
        self._mw = PicoAmmeterGUIMainWindow()
        # Configure PlotWidget
        self._pw = self._mw.data_trace_PlotWidget
        self._pw.setLabel('bottom', 'Time', units='s')
        self._pw.setMouseEnabled(x=True, y=True)
        self._pw.setMouseTracking(True)
        self._pw.setMenuEnabled(True)
        self._pw.hideButtons()

        # set default params
        if self._picoammeter_logic.pico_connection != None:
            self._picoammeter_logic.set_current_range(0) #set current range to 2na
            self._picoammeter_logic.set_voltage_range(0) #set voltage range to +- 10v
            self._picoammeter_logic.set_voltage_value(0) #set voltage value to 0V

        #set entry limits
        self._mw.voltage_value_box.setMaximum(10)


        # connecting user interations
        self._mw.voltage_on_off_checkbox.stateChanged.connect(self.voltage_on_off_changed)
        self.sigVoltage.connect(self._picoammeter_logic.set_voltage_state)
        self._mw.voltage_range_box.currentIndexChanged.connect(self.voltage_range_changed)
        self.sigVRangeChange.connect(self._picoammeter_logic.set_voltage_range)
        self._mw.current_range_box.currentIndexChanged.connect(self.current_range_changed)
        self.sigCRangeChange.connect(self._picoammeter_logic.set_current_range)

        self._mw.set_voltage_button.clicked.connect(self.set_voltage_button_clicked)
        self.sigVValueChange.connect(self._picoammeter_logic.set_voltage_value)
        return

    def show(self):
        """Make window visible and put it above all other windows.
        """
        QtWidgets.QMainWindow.show(self._mw)
        self._mw.activateWindow()
        self._mw.raise_()
        return

    def on_deactivate(self):
        self._mw.close()
        return

    @QtCore.Slot(int)
    def voltage_on_off_changed(self):
        self.sigVoltage.emit(self._mw.voltage_on_off_checkbox.isChecked())
        if self._mw.voltage_on_off_checkbox.isChecked():
            self._mw.statusBar().showMessage('Voltage 1')
        else:
            self._mw.statusBar().showMessage('Voltage 0')

    @QtCore.Slot(int)
    def voltage_range_changed(self):
        self.sigVRangeChange.emit(self._mw.voltage_range_box.currentIndex())
        time.sleep(0.1)
        self._mw.voltage_value_box.setMaximum(int(self._picoammeter_logic.get_voltage_range().value))
        self._mw.statusBar().showMessage("Voltage range set to: " + str(self._mw.voltage_range_box.currentText()))

    def current_range_changed(self):
        self.sigCRangeChange.emit(self._mw.current_range_box.currentIndex())
        self._mw.statusBar().showMessage("Current range set to: " + str(self._mw.current_range_box.currentText()))

    @QtCore.Slot(bool)
    def set_voltage_button_clicked(self):
        self.sigVValueChange.emit(int(self._mw.voltage_value_box.text()))
        self._mw.statusBar().showMessage("Voltage set to: " + str(self._mw.voltage_value_box.text()) + " V")
        return
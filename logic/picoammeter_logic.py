from qtpy import QtCore
import numpy as np
import datetime as dt
import time
import matplotlib.pyplot as plt

from core.connector import Connector
from core.statusvariable import StatusVar
from core.configoption import ConfigOption
from logic.generic_logic import GenericLogic
from core.util.mutex import Mutex
from core.util.units import ScaledFloat
from interface.data_instream_interface import StreamChannelType, StreamingMode
from interface.picoammeter_interface import VoltageState

class PicoAmmeterLogic(GenericLogic):
    sigUpdate = QtCore.Signal()
    picoammeter = Connector(interface='PicoAmmeterInterface')

    def on_activate(self):
        self._picoammeter = self.picoammeter()
        self.pico_connection = self._picoammeter._inst

        self.voltage_state = self._picoammeter.get_voltage_state()
        self.voltage_range = self._picoammeter.get_voltage_range()
        self.voltage_value = self._picoammeter.get_voltage_value()
        self.current_range = self._picoammeter.get_current_range()

        return

    def on_deactivate(self):
        return

    @QtCore.Slot(bool)
    def set_voltage_state(self, state):
        if state and self._picoammeter.get_voltage_state() == VoltageState.OFF:
            self._picoammeter.on()
            print('voltage on')
        if not state and self._picoammeter.get_voltage_state() == VoltageState.ON:
            self._picoammeter.off()
            print('voltage off')

        self.sigUpdate.emit()
        return

    @QtCore.Slot(int)
    def set_voltage_range(self, index):
        self._picoammeter.set_voltage_range(index)
        return

    def get_voltage_range(self):
        return self._picoammeter.get_voltage_range()

    @QtCore.Slot(int)
    def set_current_range(self, index):
        self._picoammeter.set_current_range(index)
        return self._picoammeter.get_current_range()

    def get_current_range(self):
        return self._picoammeter.get_current_range()

    @QtCore.Slot(bool)
    def set_voltage_value(self, value):
        self._picoammeter.set_voltage_value(value)
        return self._picoammeter.get_voltage_value()

    def get_voltage_value(self):
        return self._picoammeter.get_voltage_value()

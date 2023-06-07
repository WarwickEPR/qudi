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

class MicrowaveControllerLogic(GenericLogic):
    sigUpdate = QtCore.Signal()
    microwavecontroller = Connector(interface='MicrowaveControllerInterface')

    def on_activate(self):
        self._microwavecontroller = self.microwavecontroller()
        return

    def on_deactivate(self):
        return

    def set_freq(self, value):
        self._microwavecontroller.set_freq(value)
        return

    def set_power(self, value):
        self._microwavecontroller.set_power(value)
        return

    def toggle_power(self, value):
        self._microwavecontroller.toggle_power(value)
        return

    def start_sweep(self):
        return

    def define_sweep(self):
        return

    def set_sweep_params(self):
        return
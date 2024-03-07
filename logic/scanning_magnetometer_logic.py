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

class ScanningMagnetometerLogic(GenericLogic):
    sigUpdate = QtCore.Signal()
    scanningmagnetometercontroller = Connector(interface='ScanningMagnetometerInterface')

    def on_activate(self):
        self._scanningmagnetometercontroller = self.scanningmagnetometercontroller()
        return

    def on_deactivate(self):
        return

    def connectMW(self, ipAddress):
        self._scanningmagnetometercontroller.connectMW(ipAddress)
        return

    def connectStage(self, comPort):
        self._scanningmagnetometercontroller.connectStage(comPort)

    def homeStage(self):
        self._scanningmagnetometercontroller.homeStage()
    def setStagePos(self,x,y):
        self._scanningmagnetometercontroller.setStagePos(x,y)
    def setStageHeight(self,z):
        self._scanningmagnetometercontroller.setStageHeight(z)


    def set_freq(self, value):
        self._scanningmagnetometercontroller.set_freq(value)
        return

    def set_power(self, value):
        self._scanningmagnetometercontroller.set_power(value)
        return

    def toggle_power(self, value):
        self._scanningmagnetometercontroller.toggle_power(value)
        return

    def start_sweep(self):
        return

    def define_sweep(self):
        return

    def set_sweep_params(self):
        return
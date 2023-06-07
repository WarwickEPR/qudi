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



class MicrowaveControllerGUIMainWindow(QtWidgets.QMainWindow):
    def __init__(self, **kwargs):
        this_dir = os.path.dirname(__file__)
        ui_file = os.path.join(this_dir, 'microwave_gui.ui')

        super().__init__(**kwargs)
        uic.loadUi(ui_file, self)
        self.show()

class MicrowaveControllerGUI(GUIBase):
    microwavecontrollerlogic = Connector(interface='MicrowaveControllerLogic')

    sigSetFreq = QtCore.Signal(float)
    sigSetPower = QtCore.Signal(float)
    sigTogglePower = QtCore.Signal(bool)
    sigStartSweep = QtCore.Signal()
    sigSweepDef = QtCore.Signal()
    sigSetSweepParams = QtCore.Signal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._mw = None
        self._pw = None
        return

    def on_activate(self):
        self._microwavecontrollerlogic = self.microwavecontrollerlogic()
        self._mw = MicrowaveControllerGUIMainWindow()


        #create connections and signals
        self._mw.setFreqBtn.clicked.connect(self.set_freq)
        self.sigSetFreq.connect(self._microwavecontrollerlogic.set_freq)

        self._mw.setPwrBtn.clicked.connect(self.set_power)
        self.sigSetPower.connect(self._microwavecontrollerlogic.set_power)

        self._mw.togglePwrChk.stateChanged.connect(self.toggle_power)
        self.sigTogglePower.connect(self._microwavecontrollerlogic.toggle_power)

        self._mw.startSwpBtn.clicked.connect(self.start_sweep)
        self.sigSetFreq.connect(self._microwavecontrollerlogic.start_sweep)

        self._mw.sweepDefBox.currentIndexChanged.connect(self.define_sweep)
        self.sigSweepDef.connect(self._microwavecontrollerlogic.define_sweep)

        self._mw.setSweepParamBtn.clicked.connect(self.set_sweep_params)
        self.sigSetSweepParams.connect(self._microwavecontrollerlogic.set_sweep_params)



        return

    def on_deactivate(self):
        return

    def show(self):
        """Make window visible and put it above all other windows.
        """
        QtWidgets.QMainWindow.show(self._mw)
        self._mw.activateWindow()
        self._mw.raise_()
        return

    def set_freq(self):
        self.sigSetFreq.emit(self._mw.freqBox.value())
        return

    def set_power(self):
        self.sigSetPower.emit(self._mw.pwrBox.value())
        return

    def toggle_power(self):
        self.sigTogglePower.emit(self._mw.togglePwrChk.isChecked())
        return

    def start_sweep(self):
        self.sigStartSweep.emit()
        return
    
    def define_sweep(self):
        self.sigSweepDef.emit(self._mw.sweepDefBox.currentIndex())
        return

    def set_sweep_params(self):
        self.sigSetSweepParams.emit()
        return
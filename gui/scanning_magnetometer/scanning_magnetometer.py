import os
import serial
import serial.tools.list_ports
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


class ScanningMagnetometerGUIMainWindow(QtWidgets.QMainWindow):
    def __init__(self, **kwargs):
        this_dir = os.path.dirname(__file__)
        ui_file = os.path.join(this_dir, 'scanning_magnetometer.ui')

        super().__init__(**kwargs)
        uic.loadUi(ui_file, self)
        self.show()


class ScanningMagnetometerUI(GUIBase):
    scanningmagnetometerlogic = Connector(interface='ScanningMagnetometerLogic')


    # ---- Stage control signals ---- #
    sigConnectMW = QtCore.Signal(str)
    sigConnectStage = QtCore.Signal(str)
    sigHomeStage = QtCore.Signal()
    sigSetStagePos = QtCore.Signal(float,float)
    sigSetStageHeight = QtCore.Signal(float)

    # ---- RF source control signals ---- #

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
        self._scanningmagnetometerlogic = self.scanningmagnetometerlogic()
        self._mw = ScanningMagnetometerGUIMainWindow()

        #setup connections and signals

            # ---- Stage control signals ---- #
        self._mw.connectMWSourceButton.clicked.connect(self.connectMW)
        self.sigConnectMW.connect(self._scanningmagnetometerlogic.connectMW)

        self._mw.connectStageButton.clicked.connect(self.connectStage)
        self.sigConnectStage.connect(self._scanningmagnetometerlogic.connectStage)

        self._mw.homeStageButton.clicked.connect(self.homeStage)
        self.sigHomeStage.connect(self._scanningmagnetometerlogic.homeStage)

        self._mw.setPositionButton.clicked.connect(self.setStagePos)
        self.sigSetStagePos.connect(self._scanningmagnetometerlogic.setStagePos)

        self._mw.setStageHeightButton.clicked.connect(self.setStageHeight)
        self.sigSetStageHeight.connect(self._scanningmagnetometerlogic.setStageHeight)

            # ---- RF source control signals ---- #

        self._mw.setFreqBtn.clicked.connect(self.set_freq)
        self.sigSetFreq.connect(self._scanningmagnetometerlogic.set_freq)

        self._mw.setPwrBtn.clicked.connect(self.set_power)
        self.sigSetPower.connect(self._scanningmagnetometerlogic.set_power)

        self._mw.togglePwrChk.stateChanged.connect(self.toggle_power)
        self.sigTogglePower.connect(self._scanningmagnetometerlogic.toggle_power)

        self._mw.startSwpBtn.clicked.connect(self.start_sweep)
        self.sigSetFreq.connect(self._scanningmagnetometerlogic.start_sweep)

        self._mw.sweepDefBox.currentIndexChanged.connect(self.define_sweep)
        self.sigSweepDef.connect(self._scanningmagnetometerlogic.define_sweep)

        self._mw.setSweepParamBtn.clicked.connect(self.set_sweep_params)
        self.sigSetSweepParams.connect(self._scanningmagnetometerlogic.set_sweep_params)

        try:
            ports = serial.tools.list_ports.comports()
            availablePorts = []
            for port, desc, hwid in sorted(ports):
                availablePorts.append("{}".format(port))
            test = self._mw.comPortBox
            test.addItems(availablePorts)
        except Exception as error:
            print("ERROR: Could not populate COM port list")
            print(error)
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

    def connectMW(self):
        self.sigConnectMW.emit(self._mw.MWSourceIPAddressBox.text())
        return

    def connectStage(self):
        self.sigConnectStage.emit(self._mw.comPortBox.currentText())

    def homeStage(self):
        self.sigHomeStage.emit()

    def setStagePos(self):
        self.sigSetStagePos.emit(self._mw.xPosSpinBox.value(), self._mw.yPosSpinBox.value())

    def setStageHeight(self):
        self.sigSetStageHeight.emit(self._mw.zPosSpinBox.value())

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
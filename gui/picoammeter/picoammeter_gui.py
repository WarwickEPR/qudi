import numpy as np
import os
import pyqtgraph as pg
import time
import math

from core.connector import Connector
from gui.colordefs import QudiPalettePale as palette
from gui.guibase import GUIBase
from hardware.picoammeter.keithley_hardware import VoltageRange
from interface.picoammeter_interface import PicoammeterInterface
from qtpy import QtCore
from qtpy import QtWidgets
from qtpy import uic

class PicoammeterWindow(QtWidgets.QMainWindow):
    """ Create the Main Window based on the *.ui file. """
    def __init__(self):
        # Get the path to the *.ui file
        this_dir = os.path.dirname(__file__)
        ui_file = os.path.join(this_dir, 'picoammeter_gui.ui')

        # Load it
        super().__init__()
        uic.loadUi(ui_file, self)
        self.show()

class PicoammeterGUI(GUIBase):
    picoammeterlogic = Connector(interface='PicoammeterLogic')

    sigSetVoltage = QtCore.Signal(float)
    sigOperateVoltage = QtCore.Signal(bool)
    sigVoltageRange = QtCore.Signal(int)
    sigReadCurrent = QtCore.Signal(bool)
    sigZeroCheck = QtCore.Signal()
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def on_activate(self):
        self.mw = PicoammeterWindow()
        self._picoammeterlogic = self.picoammeterlogic()

        self.mw.SetVoltageButton.clicked.connect(self.setvoltage)
        self.sigSetVoltage.connect(self._picoammeterlogic.set_voltage)

        self.mw.OperateVoltage.stateChanged.connect(self.togglevoltage)
        self.sigOperateVoltage.connect(self._picoammeterlogic.toggle_voltage)

        self.mw.VoltageRange.currentIndexChanged.connect(self.voltagerangechange)
        self.sigVoltageRange.connect(self._picoammeterlogic.voltage_range_change)

        self.mw.Measurement.stateChanged.connect(self.measurementtoggle)
        self.sigReadCurrent.connect(self._picoammeterlogic.measurement_toggle)

        self._picoammeterlogic.sigUpdate.connect(self.updatecurrent)

        self.mw.CurrentMeasure.setText("0")

        self.mw.ZeroButton.clicked.connect(self.zerocheck)
        self.sigZeroCheck.connect(self._picoammeterlogic.zero_check)


        #setting up plot
        self._pw = self.mw.trace_PlotWidget

        self.plot1 = self._pw.plotItem
        self.plot1.setLabel('left', 'Current', units='A', color='#00ff00')
        self.plot1.setLabel('bottom', 'Time', units='s')

        self.curve = pg.PlotDataItem()
        self.curve.setPen(palette.c1)
        self.plot1.addItem(self.curve)
        return

    def on_deactivate(self):
        return

    def setvoltage(self):
        self.sigSetVoltage.emit(self.mw.SetVoltage.value())

    def togglevoltage(self):
        self.sigOperateVoltage.emit(self.mw.OperateVoltage.isChecked())

    def voltagerangechange(self):
        self.sigVoltageRange.emit(self.mw.VoltageRange.currentIndex())

    def measurementtoggle(self):
        self.sigReadCurrent.emit(self.mw.Measurement.isChecked())

    def updatecurrent(self):
        self.mw.CurrentMeasure.setText(self.to_si(self._picoammeterlogic.currentmeasurement) + 'A')
        self.curve.setData(x=self._picoammeterlogic.timearray, y=self._picoammeterlogic.currentarray)


    def zerocheck(self):
        self.sigZeroCheck.emit()

    def to_si(self, d, sep=' '):
        inc_prefixes = ['k', 'M', 'G', 'T', 'P', 'E', 'Z', 'Y']
        dec_prefixes = ['m', 'µ', 'n', 'p', 'f', 'a', 'z', 'y']

        if d == 0:
            return str(0)

        degree = int(math.floor(math.log10(math.fabs(d)) / 3))

        prefix = ''

        if degree != 0:
            ds = degree / math.fabs(degree)
            if ds == 1:
                if degree - 1 < len(inc_prefixes):
                    prefix = inc_prefixes[degree - 1]
                else:
                    prefix = inc_prefixes[-1]
                    degree = len(inc_prefixes)

            elif ds == -1:
                if -degree - 1 < len(dec_prefixes):
                    prefix = dec_prefixes[-degree - 1]
                else:
                    prefix = dec_prefixes[-1]
                    degree = -len(dec_prefixes)

            scaled = float(d * math.pow(1000, -degree))
            scaled = round(scaled, 2)

            s = "{scaled}{sep}{prefix}".format(scaled=scaled,
                                               sep=sep,
                                               prefix=prefix)

        else:
            s = "{d}".format(d=d)

        return s
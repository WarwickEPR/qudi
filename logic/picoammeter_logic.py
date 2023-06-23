import time
import numpy as np
from qtpy import QtCore

from core.connector import Connector
from core.configoption import ConfigOption
from logic.generic_logic import GenericLogic

class PicoammeterLogic(GenericLogic):
    picoammeter = Connector(interface='PicoammeterInterface')
    sigUpdate = QtCore.Signal()
    def on_activate(self):
        self._picoammeter = self.picoammeter()
        self.stopRequest = False
        self.timer = QtCore.QTimer()
        self.timer.setInterval(100)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.measurement_loop, QtCore.Qt.QueuedConnection)
        self.currentmeasurement = "0"
        #plot
        self.timearray = []
        self.currentarray = []
        self.initialtime = None
        return

    def on_deactivate(self):
        self.stop_measurement_loop()
        for i in range(10):
            QtCore.QCoreApplication.processEvents()
            time.sleep(100/1000)
        return

    def set_voltage(self,value):
        self._picoammeter.set_voltage(value)

    def toggle_voltage(self,value):
        if value==True:
            self._picoammeter.operate_voltage_on()
        elif value==False:
            self._picoammeter.operate_voltage_off()

    def voltage_range_change(self,value):
        self._picoammeter.set_voltage_range(value)
        if value == 0:
            self._picoammeter.set_voltage_range(10)
        if value == 1:
            self._picoammeter.set_voltage_range(50)
        if value == 2:
            self._picoammeter.set_voltage_range(500)

    def start_measurement_loop(self):
        self.initialtime = time.time()
        self.currentarray = []
        self.timearray = []
        self.module_state.run()
        self.timer.start(100)

    def stop_measurement_loop(self):
        self.stopRequest = True
        for i in range(10):
            if not self.stopRequest:
                return
            QtCore.QCoreApplication.processEvents()
            time.sleep(100/1000)

    def measurement_loop(self):
        qi = 100
        if self.stopRequest:
            if self.module_state.can('stop'):
                self.module_state.stop()
            self.stopRequest = False
            return
        try:
            self.currentmeasurement = self._picoammeter.read_current()
            self.currentmeasurement = float(self.currentmeasurement.split(',')[0][:-1])
        except:
            qi = 3000
            self.log.exception("Exception in measurement loop, throttling refresh rate.")

        self.currentarray.append(self.currentmeasurement)
        self.timearray.append(time.time()-self.initialtime)
        self.timer.start(qi)
        self.sigUpdate.emit()

    def measurement_toggle(self,value):
        if value==True:
            self.start_measurement_loop()
        elif value==False:
            self.stop_measurement_loop()

    def zero_check(self):
        self._picoammeter.zero()


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

        self.sweepTimer = QtCore.QTimer()
        self.sweepTimer.setInterval(30000)
        self.sweepTimer.setSingleShot(True)
        self.sweepTimer.timeout.connect(self._update_sweep_voltage, QtCore.Qt.QueuedConnection)
        self.sweep_voltages = None
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

    def begin_voltage_sweep(self, voltage_start, voltage_stop, voltage_step, step_interval_in_ms, symmetric_sweep):
        """
        Sweeps the voltage and measures for the given dwell time at each voltage. If symmetric_sweep is true,
        the voltage will run from 0 to -voltage_stop to 0 to + voltage_stop to 0. Voltage_stop should be positive.
        If symmetric_sweep is false, the voltage will run from voltage_start to voltage_stop.
        """
        if symmetric_sweep is False:
            self.sweep_voltages = np.linspace(voltage_start, voltage_stop, int((voltage_stop-voltage_start)/voltage_step + 1))
        else:
            voltage_stop: int = round(np.abs(voltage_stop))
            sweep_down_from_zero = np.linspace(0, -voltage_stop, int((voltage_stop) / voltage_step + 1))
            sweep_up_to_zero = np.flip(sweep_down_from_zero, 0)[1:-1]
            sweep_up_from_zero = -sweep_down_from_zero
            sweep_down_to_zero = np.flip(sweep_up_from_zero, 0)[1:]
            self.sweep_voltages = np.concatenate((sweep_down_from_zero, sweep_up_to_zero, sweep_up_from_zero, sweep_down_to_zero))

        self.sweepTimer.setInterval(step_interval_in_ms)
        self.sweep_index = 0

        self.stop_measurement_loop()
        self.set_voltage(self.sweep_voltages[0])
        self.start_measurement_loop()
        self.sweepTimer.start()

    def _update_sweep_voltage(self):
        if self.sweep_index + 1 == len(self.sweep_voltages):
            self.stop_measurement_loop()
        else:
            self.sweep_index += 1
            self.set_voltage(self.sweep_voltages[self.sweep_index])
            self.sweepTimer.start()


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


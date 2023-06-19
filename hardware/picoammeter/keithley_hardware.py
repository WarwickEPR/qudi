import os
import sys
import serial
import re
import numpy as np
from enum import Enum
import time
import logging as log
log.basicConfig( level = log.DEBUG )
from core.module import Base
from core.configoption import ConfigOption
from interface.picoammeter_interface import PicoammeterInterface
from PyQt5 import QtCore
from core.util.mutex import Mutex

import visa


class VoltageRange(Enum):
    V1 = '10'
    V2 = '50'
    V3 = '500'


class PicoammeterException(Exception):
    def __init__(self, *args, **kwargs):
        super(PicoammeterException, self).__init__(*args)


class PicoammeterHardware(Base, PicoammeterInterface):
    _address = ConfigOption('pico_address', missing='error')
    SourceVolt = "SOUR:VOLT"
    SWEEPING = 1 << 3

    sigOpConditionChanged = QtCore.Signal(int)
    sigSweepDataUpdated = QtCore.Signal()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.inst = None
        self._timer = QtCore.QTimer()
        self._threadlock = Mutex()
        self._op_condition = 0
        self._sweep_current = []
        self._sweep_voltage = []

    def on_activate(self):
        rm = visa.ResourceManager()

        try:
            self.inst = rm.open_resource(self._address)
            self.inst.timeout = 5000
            self.write("*RST;*CLS")
            time.sleep(3)
            self.query("*OPC?")
            self._timer.setSingleShot(False)
            with self._threadlock:
                self._timer.timeout.connect(self._operation_poll)
            self.sigOpConditionChanged.connect(self._finish_sweep)

        except:
            self.log.error('Could not connect')

        self.zero()

    def on_deactivate(self):
        self.operate_voltage_off()
        self.sigOpConditionChanged.disconnect()
        self._timer.stop()
        self._timer.disconnect()
        #self.sigSweepDataUpdated.disconnect()
        self.inst.close()

    def write(self, msg):
        if self.inst is None:
            raise Exception('Can not write, instrument not connected.')

        return self.inst.write(msg)

    def query(self, msg):
        if self.inst is None:
            raise Exception('Can not query, instrument not connected')

        return self.inst.query(msg).rstrip()

    def set_voltage_range(self, value):
        self.write(self.SourceVolt + f':RANG {value}')

    def operate_voltage_on(self):
        self.write(self.SourceVolt + ':STAT ON')

    def operate_voltage_off(self):
        self.write(self.SourceVolt + ':STAT OFF')

    def set_voltage(self, value):
        self.write(self.SourceVolt + f' {value}')

    def read_current(self):
        return self.query('READ?')

    def sweep(self, start=-10.0, end=10.0, points=1024, sweep_delay=0.1):
        self._start_sweep(start, end, points, sweep_delay)
        self._start_status_poll()

    def _start_sweep(self, start=-10.0, end=10.0, points=1024, sweep_delay=0.1):
        if points < 2:
            raise PicoammeterException("Insufficient points: {}".format(points))
        step = (end-start)/float(points-1)
        self.write('*RST')
        self.write('CURR:NPLC 1')
        self.write('RANGE 0.02')
        self.write('SOURCE:VOLT:SWEEP:START {}'.format(start))
        self.write('SOURCE:VOLT:SWEEP:STOP {}'.format(end))
        self.write('SOURCE:VOLT:SWEEP:STEP {}'.format(step))
        self.write('SOURCE:VOLT:SWEEP:DEL {}'.format(sweep_delay))
        self.write('ARM:COUNT INF')
        self.write('TRIG:SOURCE IMM')
        self.write("FORM:ELEM READ,VSO")
        self.write('SOURCE:VOLT:SWEEP:INIT')
        self.write('SYST:ZCH OFF')
        self.write(':INIT:IMM')
        self.log.info("Sweep started")

    def _start_status_poll(self):
        self._timer.start(1000)  # 1s

    def _stop_status_poll(self):
        self._timer.stop()

    def _is_sweeping(self):
        return bool(self._op_condition & self.SWEEPING)

    def _finish_sweep(self):
        if not self._is_sweeping():
            self.log.info("Sweep finished, retrieving data")
            self._stop_status_poll()
            self.write(":ABORT; *OPC")
            self._retrieve_sweep_data()

    def _retrieve_sweep_data(self):
        data = self.query("TRACE:DATA?").split(',')
        current = [float(x) for x in data[0::2]]
        voltage = [float(x) for x in data[1::2]]
        self._sweep_current = np.array(current)
        self._sweep_voltage = np.array(voltage)
        self.sigSweepDataUpdated.emit()

    def _operation_poll(self):
        _op_condition = int(self.query("STATUS:OPERATION:CONDITION?"))
        if _op_condition != self._op_condition:
            self.log.debug("Operation status register changed from {} to {}".format(self._op_condition, _op_condition))
            self._op_condition = _op_condition
            self.sigOpConditionChanged.emit(_op_condition)

    def _poll_sweeping(self):
        opstatus = int(self.query("STATUS:OPERATION:CONDITION?"))


    def _abort(self):
        self.write(":ABORT")


    def zero(self):
        self.write('*RST')
        self.write("FUNC 'CURR'")
        self.write('SYST:ZCH ON')
        self.write('CURR:RANG 2e-9')
        self.write('INIT')
        self.write('SYST:ZCOR:STAT OFF')
        self.write('SYST:ZCOR:ACQ')
        self.write('SYST:ZCOR ON')
        self.write('CURR:RANG:AUTO ON')
        self.write('SYST:ZCH OFF')
        
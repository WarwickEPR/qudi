import os
import sys
import serial
import re
from enum import Enum
import time
import logging as log
log.basicConfig( level = log.DEBUG )
from core.module import Base
from core.configoption import ConfigOption
from interface.picoammeter_interface import PicoammeterInterface

import visa


class VoltageRange(Enum):
    V1 = '10'
    V2 = '50'
    V3 = '500'

class PicoammeterHardware(Base, PicoammeterInterface):
    _address = ConfigOption('pico_address', missing='error')
    SourceVolt = "SOUR:VOLT"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.inst = None

    def on_activate(self):
        rm = visa.ResourceManager()

        try:
            self.inst = rm.open_resource(self._address)
            self.write("*RST;*CLS")
            time.sleep(3)
            self.query("*OPC?")
        except:
            self.log.error('Could not connect')

        self.zero()

    def on_deactivate(self):
        self.operate_voltage_off()
        self.inst.close()

    def write(self, msg):
        if self.inst is None:
            raise Exception('Can not write, instrument not connected.')
            return

        return self.inst.write(msg)

    def query(self, msg):
        if self.inst is None:
            raise Exception('Can not query, instrument not connected')

        return self.inst.query(msg)

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
        
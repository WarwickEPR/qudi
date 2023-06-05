import visa
import math
import random
import time

from core.module import Base
from core.configoption import ConfigOption
from interface.picoammeter_interface import PicoAmmeterInterface
from interface.picoammeter_interface import VoltageState, VoltageRange, CurrentRange


class PicoAmmeterHardware(Base, PicoAmmeterInterface):
    _address = ConfigOption('pico_address', missing='error')

    def __init__(self, **kwargs):
        """ """
        super().__init__(**kwargs)
        self.model = None
        self._inst = None
        self.vstate = VoltageState.OFF
        self.vrange = VoltageRange._10
        self.vvalue = 0
        self.crange = CurrentRange._2na

    def on_activate(self):
        """ Activate module.
        """
        rm = visa.ResourceManager()
        try:
            self._inst = rm.open_resource(self._address)
            self.model = self._query('*IDN?').split(',')[1]  # get unit identification
            self._write("*RST;*CLS")  # reset device to default conditions and clear registers/error queues
            time.sleep(3)
            """
            operation complete query - places ASCII '1' into output queue when all pending operations are completed
            """
            self._query("*OPC?")
        except:
            self.log.error('Could not connect to hardware, check connection and address')

    def on_deactivate(self):
        """ Deactivate module.
        """
        self._write("SOUR:VOLT:STAT OFF")
        self._inst.close()
        pass

    def _write(self, cmd):
        """ Function to write command to hardware"""
        self._inst.write(cmd)
        time.sleep(.01)

    def _query(self, cmd):
        """ Function to query hardware"""
        return self._inst.query(cmd)

    def set_voltage_state(self, state):
        print(state)
        time.sleep(1)
        self.vstate = state
        return self.vstate

    def get_voltage_state(self):
        return self.vstate

    def set_voltage_range(self, index):
        if index == 0:
            self.vrange = VoltageRange._10
            self._write("SOUR:VOLT:RANG 10")
        elif index == 1:
            self.vrange = VoltageRange._50
            self._write("SOUR:VOLT:RANG 50")
        elif index == 2:
            self.vrange = VoltageRange._500
            self._write("SOUR:VOLT:RANG 500")
        return self.vrange

    def get_voltage_range(self):
        return self.vrange

    def set_current_range(self, index):
        if index == 0:
            self.crange = CurrentRange._2na
        elif index == 3:
            self.crange = CurrentRange._20na
        elif index == 2:
            self.crange = CurrentRange._200na
        elif index == 3:
            self.crange = CurrentRange._2ua
        elif index == 4:
            self.crange = CurrentRange._20ua
        elif index == 5:
            self.crange = CurrentRange._200ua
        elif index == 6:
            self.crange = CurrentRange._2ma
        elif index == 6:
            self.crange = CurrentRange._20ma
        return self.crange

    def get_current_range(self):
        return self.crange

    def set_voltage_value(self, value):
        self.vvalue = value
        return self.vvalue

    def get_voltage_value(self):
        return self.vvalue

    def on(self):
        time.sleep(1)
        self.vstate = VoltageState.ON
        return self.vstate

    def off(self):
        time.sleep(1)
        self.vstate = VoltageState.OFF
        return self.vstate

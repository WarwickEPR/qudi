import visa
import math
import random
import time

from core.module import Base
from core.configoption import ConfigOption
from interface.microwave_controller_interface import MicrowaveControllerInterface
from interface.picoammeter_interface import VoltageState, VoltageRange, CurrentRange
from qtpy import QtWidgets


class MicrowaveControllerHardware(Base, MicrowaveControllerInterface):
    _address = ConfigOption('microwave_address', missing='error')

    def __init__(self, **kwargs):
        """ """
        super().__init__(**kwargs)
        self.model = None
        self._inst = None

    def on_activate(self):
        """ Activate module.
        """
        try:
            rm = visa.ResourceManager()
            print(self._address)
            print(self._address)
            self.inst = rm.open_resource(self._address)
            self.inst.chunk_size = 102400
            self.inst.write("*CLS")  # clear error bank
            self.inst.baud_rate = 115200
            self.model = self.inst.query('*IDN?').split(',')[1]  # get unit identification
            self.inst.write("*RST;*CLS")  # reset device to default conditions and clear registers/error queues
            time.sleep(3)
            """
            operation complete query - places ASCII '1' into output queue when all pending operations are completed
            """
            self.inst.query("*OPC?")
        except:
            print("could not connect")

    def on_deactivate(self):
        """ Deactivate module.
        """
        self._inst.close()
        pass

    def set_freq(self, value):
        self.inst.write('FREQ ' + str(value * 1e9))
        return

    def set_power(self, value):
        self.inst.write(f'POW {value} dBm')
        return

    def toggle_power(self, value):
        if value == 0:
            self.inst.write('OUTP OFF')
        elif value == 1:
            self.inst.write('OUTP ON')
        return

    def start_sweep(self):
        return

    def define_sweep(self):
        return

    def set_sweep_params(self):
        return
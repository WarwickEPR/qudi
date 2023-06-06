import visa
import math
import random
import time

from core.module import Base
from core.configoption import ConfigOption
from interface.microwave_controller_interface import MicrowaveControllerInterface
from interface.picoammeter_interface import VoltageState, VoltageRange, CurrentRange


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
        self._inst.close()
        pass
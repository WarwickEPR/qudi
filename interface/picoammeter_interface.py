from enum import Enum
from core.interface import abstract_interface_method
from core.meta import InterfaceMetaclass


class VoltageState(Enum):
    OFF = 0
    ON = 1


class VoltageRange(Enum):
    _10 = 10
    _50 = 50
    _500 = 500

class CurrentRange(Enum):
    _2na = 0
    _20na = 1
    _200na = 2
    _2ua = 3
    _20ua = 4
    _200ua = 5
    _2ma = 6
    _20ma = 7

class PicoAmmeterInterface(metaclass=InterfaceMetaclass):

    @abstract_interface_method
    def set_voltage_state(self, state):
        """ Set voltage state.
                  @param enum state: desired voltage state
                  @return enum LaserState: actual voltage state
        """
        pass

    @abstract_interface_method
    def get_voltage_state(self):
        pass

    @abstract_interface_method
    def set_voltage_range(self):
        pass

    @abstract_interface_method
    def get_voltage_range(self):
        pass

    @abstract_interface_method
    def set_current_range(self):
        pass

    @abstract_interface_method
    def get_current_range(self):
        pass

    @abstract_interface_method
    def set_voltage_value(self):
        pass

    @abstract_interface_method
    def get_voltage_value(self):
        pass

    @abstract_interface_method
    def on(self):
        pass

    @abstract_interface_method
    def off(self):
        pass

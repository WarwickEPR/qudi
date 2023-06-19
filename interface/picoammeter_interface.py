from enum import Enum
import abc
from core.meta import InterfaceMetaclass


class PicoammeterInterface(metaclass=InterfaceMetaclass):
    _modtype = 'PicoammeterInterface'
    _modclass = 'interface'

    @abc.abstractmethod
    def zero(self):
        """Zeros internal current
        return ??? nothing maybe?"""  # what should this return?
        pass

    @abc.abstractmethod
    def set_voltage(self, value):
        """Set voltage in volts
        input float: voltage in volts
        return float: voltage in volts"""
        pass

    @abc.abstractmethod
    def operate_voltage_on(self):
        """Turn voltage on
        return boolean: on - including permanent indicator"""
        pass

    @abc.abstractmethod
    def operate_voltage_off(self):
        """Turn voltage off
        return boolean: off - including permanent indicator"""
        pass

    @abc.abstractmethod
    def set_voltage_range(self, value):
        """set voltage range
        return float: maximum voltage on volts"""
        pass

    @abc.abstractmethod
    def read_current(self):
        """Read measured current
        return float: current in amps"""
        pass
from enum import Enum
from core.interface import abstract_interface_method
from core.meta import InterfaceMetaclass


class MicrowaveControllerInterface(metaclass=InterfaceMetaclass):

    @abstract_interface_method
    def set_freq(self):
        return

    @abstract_interface_method
    def set_power(self):
        return

    @abstract_interface_method
    def toggle_power(self):
        return

    @abstract_interface_method
    def start_sweep(self):
        return

    @abstract_interface_method
    def define_sweep(self):
        return

    @abstract_interface_method
    def set_sweep_params(self):
        return
import pyvisa
import serial
from core.module import Base
from core.configoption import ConfigOption
from interface.scanning_magnetometer_interface import ScanningMagnetometerInterface
from qtpy import QtWidgets


class ScanningMagnetometerHardware(Base, ScanningMagnetometerInterface):

    def __init__(self, **kwargs):
        """ """
        super().__init__(**kwargs)
        self.model = None
        self._inst = None

    def on_activate(self):
        """ Activate module.
        """
        return

    def on_deactivate(self):
        """ Deactivate module.
        """
        self._inst.close()
        pass

    # ---- Stage Control ---- #

    def connectStage(self, comPort):
        try:
            self.ser = serial.Serial(port=comPort, baudrate=115200)  # printer connect
        except:
            print("EEROR: Could not connect to stage")

    def homeStage(self):
        self.executeGCode('G28') #home gcode
        return

    def setStagePos(self,x,y):
        print(x,y)
        self.executeGCode(f'G00 X{x} Y{y}')
        return

    def setStageHeight(self,z):
        print(z)
        self.executeGCode(f'G00 Z{z}')
        return

    def executeGCode(self, command):
        try:
            self.ser.write(f'{command}\r\n'.encode())
        except:
            print("ERROR: Could not execute stage command")

    # ---- RF Source Control ---- #

    def connectMW(self, ipAddress):
        try:
            fullAddress = "TCIP::" + ipAddress + "::INSTR"
            print(fullAddress)
            self.rm = pyvisa.ResourceManager()
            self.inst = self.rm.open_resource(fullAddress)
            self.inst.chunk_size = 102400
            self.inst.write("*CLS")  # clear error bank
            self.inst.baud_rate = 115200
            self.RFconnected = True
        except:
            print('Could not connect to RF')
        return

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
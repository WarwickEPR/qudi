# Not sure why this is needed, but module will not work without it.
import ctypes
ctypes.windll.LoadLibrary("c:\\Users\\User\\Documents\\Qudi-IX\\PyANC350\\anc350v4.dll")

from PyANC350.PyANC350v4 import *

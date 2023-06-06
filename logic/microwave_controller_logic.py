from qtpy import QtCore
import numpy as np
import datetime as dt
import time
import matplotlib.pyplot as plt

from core.connector import Connector
from core.statusvariable import StatusVar
from core.configoption import ConfigOption
from logic.generic_logic import GenericLogic
from core.util.mutex import Mutex
from core.util.units import ScaledFloat
from interface.data_instream_interface import StreamChannelType, StreamingMode

class MicrowaveControllerLogic(GenericLogic):
    sigUpdate = QtCore.Signal()
    microwavecontroller = Connector(interface='MicrowaveControllerInterface')

    def on_activate(self):
        return

    def on_deactivate(self):
        return


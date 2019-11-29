from qtpy import QtCore
import time
import datetime

from logic.generic_logic import GenericLogic
from core.connector import Connector
from core.configoption import ConfigOption


def _time_str():
    return datetime.datetime.now().strftime("%Y%m%d-%H%M%S")

class OptimizerLogic(GenericLogic):

    """Helper module to simplify running survey workflow scripts in the background.
        Works in cooperatively with Jupyter"""

    # Connect to everything this module has helper methods for
    # (intended as a local module although in some form this could be made configurable)
    aom = Connector(interface='aomlogic')
    hbt = Connector(interface='hbtlogic')
    poimanager = Connector(interface='poimanagerlogic')
    pulsedmaster = Connector(interface='pulsedmasterlogic')
    optimizer = Connector(interface='optimizerlogic')

    working_directory = ConfigOption('working_directory')

    _sigInternal = QtCore.Signal()


    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)

        self._running = False   # Is a workflow running
        self._subdir = None

    def on_activate(self):
        """ Initialisation performed during activation of the module.

        @return int: error code (0:OK, -1:error)
        """
        return 0


    def on_deactivate(self):
        """ Reverse steps of activation

        @return int: error code (0:OK, -1:error)
        """
        return 0

    def run_in_background(self, code):
        # set up a namespace for the sub thread


    def wlog(self, msg):
        # log the workflow progress to a separate logfile
        out = _time_str() + ' ' + msg
        with open(self._log_file, 'a') as f:
            f.write(out + '\n')
        self.log.debug(msg)

    def set_laser_power(self, power):
        self.wlog("Setting power via AOM to {} mW".format(power))
        self.aom().set_power(power * 1e-3)


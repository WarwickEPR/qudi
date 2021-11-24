from core.connector import Connector
from logic.generic_logic import GenericLogic
from PyQt5.QtCore import Qt

class OptimizerPauseLogic(GenericLogic):

    _modclass = 'optimizerpauselogic'
    _modtype = 'logic'

    # Just plumbs in queued signals between modules. Does nothing itself after activation
    _threaded = False

    pulsed_measurement = Connector(interface='PulsedMeasurementLogic')
    optimizer = Connector(interface='OptimizerLogic')

    def on_activate(self):
        self.optimizer().sigRefocusStarted.connect(self.refocus_started, Qt.QueuedConnection)
        self.optimizer().sigRefocusFinished.connect(self.refocus_finished, Qt.QueuedConnection)

    def on_deactivate(self):
        self.optimizer().sigRefocusStarted.disconnect(self.refocus_started)
        self.optimizer().sigRefocusFinished.disconnect(self.refocus_finished)

    def refocus_started(self, _):
        self.pulsed_measurement().pause_pulsed_measurement()

    def refocus_finished(self, _, _):
        self.pulsed_measurement().continue_pulsed_measurement()


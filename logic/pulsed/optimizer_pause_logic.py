from core.connector import Connector
from logic.generic_logic import GenericLogic
from PyQt5.QtCore import Qt


class OptimizerPauseLogic(GenericLogic):

    _modclass = 'optimizerpauselogic'
    _modtype = 'logic'

    # Just plumbs in queued signals between modules. Does nothing itself after activation
    _threaded = False

    pulsedmeasurement = Connector(interface='PulsedMeasurementLogic')
    optimizer = Connector(interface='OptimizerLogic')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._optimizer_paused = False

    def on_activate(self):
        self.optimizer().sigRefocusStarted.connect(self.refocus_started, Qt.QueuedConnection)
        self.optimizer().sigRefocusFinished.connect(self.refocus_finished, Qt.QueuedConnection)

    def on_deactivate(self):
        self.optimizer().sigRefocusStarted.disconnect(self.refocus_started)
        self.optimizer().sigRefocusFinished.disconnect(self.refocus_finished)

    def refocus_started(self, _):
        if self.pulsedmeasurement().module_state() == 'locked':
            self.pulsedmeasurement().pause_pulsed_measurement()
            self._optimizer_paused = True

    def refocus_finished(self, _, _x):
        if self._optimizer_paused:
            self.pulsedmeasurement().continue_pulsed_measurement()
            self._optimizer_paused = False


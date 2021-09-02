from . base import ZmqProxy
from core.connector import Connector
from logic.zmq.message import PubMessage, Message
from PyQt5.QtCore import Qt


class PoiProxy(ZmqProxy):

    frontend = Connector(interface='ZmqFrontend')
    poimanager = Connector(interface='PoiManagerLogic')
    pulsedmeasurement = Connector(interface='PulsedMeasurementLogic', optional=True)
    optimizer = Connector(interface='OptimizerLogic', optional=True)

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)

    def on_activate(self):
        # get hold of a handle to optimizer_logic, load if necessary
        # subscribe to key events, emit a message when done
        super().on_activate()
        self._connect_pulsed_signals()

    def _on_refocus_start(self):
        if self.pulsedmeasurement() and self.pulsedmeasurement().module_state() == 'locked':
            self.pulsedmeasurement().pause_pulsed_measurement()

    def _on_refocus_stop(self, *x):
        if self.pulsedmeasurement() and self.pulsedmeasurement().module_state() == 'locked':
            self.pulsedmeasurement().continue_pulsed_measurement()

    def _connect_pulsed_signals(self, *x):
        if self.optimizer() and self.pulsedmeasurement():
            self.optimizer().onSigRefocusStarted.connect(self._on_refocus_start, Qt.QueuedConnection)
            self.optimizer().onSigRefocusFinished.connect(self._on_refocus_stop, Qt.QueuedConnection)

    def _disconnect_pulsed_signals(self):
        if self.optimizer() and self.pulsedmeasurement():
            self.optimizer().onSigRefocusStarted.disconnect(self._on_refocus_start)
            self.optimizer().onSigRefocusFinished.disconnect(self._on_refocus_stop)

    def on_deactivate(self):
        super().on_deactivate()
        self._disconnect_pulsed_signals()

    def handle_add_pois(self, msg: Message):
        self.log.debug("Adding POIs")
        pois = msg.body.pois
        for [poi, x, y, z] in pois[:-1]:
            self.poimanager().add_poi(name=poi, position=[x, y, z], emit_change=False)
        [poi, x, y, z] = pois[-1]
        self.poimanager().add_poi(name=poi, position=[x, y, z], emit_change=True)
        self.reply_done(msg)

    def handle_save_roi(self, msg: Message):
        if msg.body and 'name' in msg.body:
            name = msg.body.name
            self.poimanager().roi_name = name
            self.log.debug("Saving ROI {}".format(name))
        else:
            self.log.debug("Saving ROI")
        self.poimanager().save_roi()

    def handle_reset_roi(self, msg: Message):
        self.log.debug("Resetting ROI")
        self.poimanager().reset_roi()
        if msg.body and 'name' in msg.body:
            self.poimanager().roi_name = msg.body.name

    def handle_start_tracking(self, msg: Message):
        poi = None
        if msg.body:
            poi = msg.body
        self.log.debug("Starting tracking {}".format(poi))
        self.poimanager().start_periodic_refocus(name=poi)

    def handle_stop_tracking(self, msg: Message):
        self.log.debug("Stopping tracking")
        self.poimanager().stop_periodic_refocus()

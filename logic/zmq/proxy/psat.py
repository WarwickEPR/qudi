from . base import ZmqProxy
from core.connector import Connector
from logic.zmq.message import PubMessage, Message


class PsatProxy(ZmqProxy):

    frontend = Connector(interface='ZmqFrontend')
    aom = Connector(interface='AomLogic')

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)

    def on_activate(self):
        # get hold of a handle to optimizer_logic, load if necessary
        # subscribe to key events, emit a message when done
        super().on_activate()
        self.aom().psat_updated.connect(self.notify_psat)

    def on_deactivate(self):
        super().on_deactivate()
        self.aom().psat_updated.disconnect(self.notify_psat)

    def handle_take_psat(self, _):
        self.aom().run_psat()

    def notify_psat(self):
        self.notify('data', body={'powers': self.aom().powers, 'measurements': self.aom().psat_data})

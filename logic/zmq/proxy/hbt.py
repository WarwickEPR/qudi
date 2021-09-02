from . base import ZmqProxy
from core.connector import Connector
from logic.zmq.message import PubMessage, Message


class HbtProxy(ZmqProxy):

    frontend = Connector(interface='ZmqFrontend')
    hbt = Connector(interface='HbtLogic')

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)

    def on_activate(self):
        # get hold of a handle to optimizer_logic, load if necessary
        # subscribe to key events, emit a message when done
        super().on_activate()
        self.hbt().updated.connect(self.notify_hbt)

    def on_deactivate(self):
        super().on_deactivate()
        self.hbt().updated.disconnect(self.notify_hbt)

    def handle_start_hbt(self, _):
        self.hbt().start()

    def handle_stop_hbt(self, _):
        self.hbt().start()

    def notify_hbt(self):
        self.notify('data', body={'t': self.hbt().t, 'g2': self.hbt().data})

from . base import ZmqProxy
from core.connector import Connector
from logic.zmq.message import PubMessage, Message
from PyQt5.QtCore import Qt


class DataProxy(ZmqProxy):

    frontend = Connector(interface='ZmqFrontend')
    backend = Connector(interface='ZmqBackend')

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)

    def on_activate(self):
        # get hold of a handle to optimizer_logic, load if necessary
        # subscribe to key events, emit a message when done
        super().on_activate()

    def on_deactivate(self):
        super().on_deactivate()

    def handle_set_session(self, msg: Message):
        self.backend().session = msg.body

    def handle_get_session(self, msg: Message):
        self.reply(msg, body=self.backend().session)

    def handle_path(self, msg: Message):
        self.reply(msg, body=self.backend().local_directory)

    def handle_copy_to_filer(self, msg: Message):
        self.backend().copy_to_remote()
        self.reply_ok(msg)


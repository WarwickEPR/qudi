from . base import ZmqProxy
from core.connector import Connector
from logic.zmq.message import PubMessage, Message
from PyQt5.QtCore import Qt


class DataProxy(ZmqProxy):

    frontend = Connector(interface='ZmqFrontend')
    storage = Connector(interface='TablesStorage')

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)

    def on_activate(self):
        super().on_activate()

    def on_deactivate(self):
        super().on_deactivate()

    def handle_open_session(self, msg: Message):
        name = msg.body.get('name', None)
        title = msg.body.get('title', None)
        self.log.debug("Changing session to {} - {}".format(name, title))
        self.storage().open_session(name=name, title=title)
        self.reply(msg, body={'name': self.storage().session_name, 'path': self.storage().local_filepath})

    def handle_close_session(self, msg: Message):
        self.storage().close_session()
        self.reply_ok(msg)

    def handle_get_session_name(self, msg: Message):
        self.reply(msg, body=self.storage().session_name)

    def handle_local_filepath(self, msg: Message):
        self.reply(msg, body=self.storage().local_filepath)

    def handle_shared_filepath(self, msg: Message):
        self.reply(msg, body=self.storage().shared_filepath)

#    def handle_copy_to_filer(self, msg: Message):
#        self.storage().copy_to_remote()
#        self.reply_ok(msg)


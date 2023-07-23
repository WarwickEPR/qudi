from . base import ZmqProxy
from core.connector import Connector
from logic.zmq.message import PubMessage, Message


# The only ZMQ backend proxy loaded by default
# General facilities such as controlling the output HDF5 binding and loading modules
class ManagerProxy(ZmqProxy):

    frontend = Connector(interface='ZmqFrontend')
    storage = Connector(interface='TablesStorage')

    def __init__(self, config, **kwargs):
        super(ManagerProxy, self).__init__(config=config, **kwargs)
        self._logic_modules_requested = set()

    def on_activate(self):
        super().on_activate()
        self._manager.sigModulesChanged.connect(self.logic_modules_loaded)

    def on_deactivate(self):
        super().on_deactivate()
        self._manager.sigModulesChanged.disconnect(self.logic_modules_loaded)

    @property
    def _loaded_logic_modules(self):
        loaded = self._manager.tree['loaded']['logic'].keys()
        return set(filter(lambda x: self._manager.isModuleLoaded('logic', x), loaded))

    def logic_modules_loaded(self):
        all_available = self._logic_modules_requested.issubset(self._loaded_logic_modules)
        self.notify('logic_modules_loaded', all_available)

    def handle_attach_data_file(self, msg: Message):
        title = msg.body.get('title', None)
        datafile = msg.body.get('file', None)
        self.log.debug("Directing HDF5 output to {} - {}".format(datafile, title))
        self.storage().attach_data_file(file=datafile, title=title)
        self.reply(msg, body=self.storage().data_file_path)

    def handle_detach_data_file(self, msg: Message):
        # Actually the file is only opened under a context on each operation but this
        self.storage().detach_data_file()
        self.reply_ok(msg)

    def handle_start_logic_module(self, msg: Message):
        module = msg.body
        self.log.debug("Checking logic module loaded {}".format(module))
        if self._manager.isModuleDefined('logic', module) and not self._manager.isModuleLoaded('logic', module):
            self.log.info("Loading module {}".format(module))
            self._logic_modules_requested.add(module)
            self._manager.startModule('logic', module)
        self.logic_modules_loaded()

    def handle_storage_attached(self, msg: Message):
        self.reply(msg, body=self.storage().attached())

    def handle_storage_file_path(self, msg: Message):
        self.reply(msg, body=self.storage().data_file_path)

from . base import ZmqProxy
from core.connector import Connector
from .. message import Message
from logic.zmq.format.hbt import HbtTable


class HbtProxy(ZmqProxy):

    frontend = Connector(interface='ZmqFrontend')
    storage = Connector(interface='TablesStorage')
    hbt = Connector(interface='HbtLogic')

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)

    def on_activate(self):
        # get hold of a handle to optimizer_logic, load if necessary
        # subscribe to key events, emit a message when done
        super().on_activate()
        #self.hbt().sigStart.connect(self.notify_start)
        #self.hbt().sigStop.connect(self.notify_stop)
        #self.hbt().sigStop.connect(self._save_hbt)

    def on_deactivate(self):
        super().on_deactivate()
        #self.hbt().sigStart.disconnect(self.notify_start)
        #self.hbt().sigStop.disconnect(self.notify_stop)
        #self.hbt().hbt_updated.disconnect(self.notify_hbt)

    def handle_start(self, _):
        self.hbt().start_hbt()

    def handle_stop(self, _):
        self.hbt().stop_hbt()

    def handle_save(self, _):
        self._save_hbt()

    def handle_save_qudi(self, msg: Message):
        if msg.body != {}:
            self.hbt().save_hbt(msg.body)
        else:
            self.hbt().save_hbt()

    def notify_start(self):
        self.notify('starting')

    def notify_stop(self):
        self.notify('stopping')
        self.notify_hbt()

    def _save_hbt(self):
        with self.storage().tables_context() as t:
            dataset = t.create_measurement_table('HBT', HbtTable)
            dataset.append(list(zip(self.hbt().bin_times, self.hbt().g2_data, self.hbt().g2_data_normalised)))
            t.flush()
        return dataset

    def notify_hbt(self):
        self.notify('data', body={'t': self.hbt().bin_times, 'g2': self.hbt().g2_data_normalised})

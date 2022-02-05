from . base import ZmqProxy
from core.connector import Connector
from .. message import Message
from logic.zmq.format.hbt import HBT


class HbtProxy(ZmqProxy):

    frontend = Connector(interface='ZmqFrontend')
    storage = Connector(interface='TablesStorage')
    hbt = Connector(interface='HbtLogic')
    poi_manager = Connector(interface='PoiManagerLogic')

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)
        self.hbt().sigStart.connect(self.notify_hbt_start)
        self.hbt().sigStop.connect(self.notify_hbt_stop)
        self.hbt().sigStop.connect(self._save_hbt)

    def on_activate(self):
        # get hold of a handle to optimizer_logic, load if necessary
        # subscribe to key events, emit a message when done
        super().on_activate()
        self.hbt().sigStart.connect(self.notify_start)
        self.hbt().sigStop.connect(self.notify_stop)
        self.hbt().sigStop.connect(self._save_hbt)

    def on_deactivate(self):
        super().on_deactivate()
        self.hbt().hbt_updated.disconnect(self.notify_hbt)

    def handle_start(self, _):
        self.hbt().start()

    def handle_stop(self, _):
        self.hbt().start()

    def handle_qudi_save(self, _):
        self.hbt().save_hbt()

    def handle_save(self, _):
        self._save_hbt()

    def notify_start(self):
        self.notify('starting')

    def notify_stop(self):
        self.notify('stopping')
        self.notify_hbt()

    def _save_hbt(self):
        with self.storage().tables_context() as t:
            poi = self.poimanager().active_poi
            dataset = t.create_measurement_table('HBT', HBT, poi)
            dataset.append(list(zip(self.hbt().bin_times, self.hbt().g2_data, self.hbt().g2_data_normalised)))
            t.flush()
        return dataset

    def notify_hbt(self):
        self.notify('data', body={'t': self.hbt().bin_times, 'g2': self.hbt().g2_data_normalised})

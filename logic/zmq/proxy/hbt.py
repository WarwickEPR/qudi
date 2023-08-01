from PyQt5.QtCore import QTimer

from . base import ZmqProxy
from core.connector import Connector
from .. message import Message
from logic.zmq.data.hbt import Hbt


class HbtProxy(ZmqProxy):

    frontend = Connector(interface='ZmqFrontend')
    storage = Connector(interface='TablesStorage')
    hbt = Connector(interface='HbtLogic')
    poimanager = Connector(interface='PoiManagerLogic')

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)
        self.timer = None

    def on_activate(self):
        # get hold of a handle to optimizer_logic, load if necessary
        # subscribe to key events, emit a message when done
        super().on_activate()
        self.hbt().sigStart.connect(self.notify_start)
        self.hbt().sigStop.connect(self.notify_stop)
        self.hbt().sigStop.connect(self._save_hbt)
        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._stop_on_timer)

    def on_deactivate(self):
        super().on_deactivate()
        self.hbt().sigStart.disconnect(self.notify_start)
        self.hbt().sigStop.disconnect(self.notify_stop)
        self.hbt().hbt_updated.disconnect(self.notify_hbt)

    def handle_start(self, _):
        self.hbt().start_hbt()

    def handle_start_timed(self, msg: Message):
        time_seconds = msg.body.get('time', 60)
        self.hbt().start_hbt()
        self.timer.start(time_seconds)

    def _stop_on_timer(self):
        self.handle_stop(None)

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

    def _save_hbt(self, tag=''):
        with self.storage().tables_context() as t:
            poi = self.poimanager().active_poi
            if not tag:
                tag = poi
            path = Hbt.node(tag=tag)
            dataset = t.create_measurement_table(Hbt.root, path, Hbt.Description)
            dataset.append(list(zip(self.hbt().bin_times, self.hbt().g2_data, self.hbt().g2_data_normalised)))
            if poi:
                dataset.attrs['poi'] = poi
            t.flush()
        return dataset

    def notify_hbt(self):
        self.notify('data', body={'t': self.hbt().bin_times, 'g2': self.hbt().g2_data_normalised})

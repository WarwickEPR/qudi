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

    def handle_emit(self, _):
        self.notify_hbt()

    def _stop_on_timer(self):
        self.handle_stop(None)

    def handle_stop(self, _):
        self.hbt().stop_hbt()
        self.notify_stopped()

    def handle_save_hdf5(self, msg: Message):
        poi = self.poimanager().active_poi
        roi = self.poimanager().roi_name
        tag = msg.body.get("tag", poi)
        bin_times = self.hbt().bin_times
        g2_raw = self.hbt().g2_data
        g2_normalised = self.hbt().g2_data_normalised
        data = Hbt(poi=poi, roi=roi, tag=tag, bin_times=bin_times, g2_normalized=g2_normalised, g2_raw=g2_raw)
        path = data.store(self.storage().tables_context())
        self.reply(msg, {'file': self.storage().local_filepath, 'path': path})

    def handle_save_qudi(self, msg: Message):
        tag = msg.body.get('tag', '')
        path = self.hbt().save_hbt(tag=tag)
        self.reply(msg, path)

    def notify_start(self):
        self.notify('hbt.starting')

    def notify_stop(self):
        self.notify('hbt.stopped')
        self.notify_hbt()

    def notify_hbt(self):
        self.notify('hbt.data', body={'t': self.hbt().bin_times, 'g2': self.hbt().g2_data_normalised})

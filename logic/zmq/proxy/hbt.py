from . base import ZmqProxy
from core.connector import Connector


class HbtProxy(ZmqProxy):

    frontend = Connector(interface='ZmqFrontend')
    storage = Connector(interface='HdfStorage')
    hbt = Connector(interface='HbtLogic')
    poi_manager = Connector(interface='PoiManager')

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

    def handle_start(self, _):
        self.hbt().start()

    def handle_stop(self, _):
        self.hbt().start()

    def handle_emit(self, _):
        self.notify_hbt()

    def handle_save(self, _):
        self.hbt().save_hbt()

    def handle_save_hdf(self, _):
        with self.storage().measurement_folder('hbt', site=self.poi_manager().active_poi) as m:
            m.create_dataset('t', data=self.hbt().t)
            m.create_dataset('g2', data=self.hbt().data)

    def notify_hbt(self):
        self.notify('data', body={'t': self.hbt().t, 'g2': self.hbt().data})

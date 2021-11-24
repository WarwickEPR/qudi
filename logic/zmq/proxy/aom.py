from . base import ZmqProxy
from core.connector import Connector
from . message import Message


class AomProxy(ZmqProxy):

    frontend = Connector(interface='ZmqFrontend')
    storage = Connector(interface='HdfStorage')
    aom = Connector(interface='AomLogic')
    poi_manager = Connector(interface='PoiManager')

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

    def handle_emit_psat(self, _):
        self.notify_psat()

    def handle_save(self, _):
        self.aom().save_psat()

    def handle_set_power(self, msg: Message):
        self.aom().set_power(msg.body)

    def handle_get_power(self, msg: Message):
        power = self.aom().get_power()
        self.reply(msg, body=power)

    def handle_save_hdf(self, _):
        with self.storage().measurement_folder('psat', site=self.poi_manager().active_poi) as m:
            m.create_dataset('powers', data=self.aom().powers)
            m.create_dataset('voltages', data=self.aom().psat_voltages)
            m.create_dataset('counts', data=self.aom().psat_data)

    def notify_hbt(self):
        self.notify('data', body={'powers': self.aom().powers,
                                  'voltages': self.aom().psat_voltages,
                                  'counts': self.aom().psat_data })

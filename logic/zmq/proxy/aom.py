from . base import ZmqProxy
from core.connector import Connector
from logic.zmq.message import Message
from logic.zmq.data.psat import Psat
from logic.zmq.data.timestamp import get_timestamp


class AomProxy(ZmqProxy):

    frontend = Connector(interface='ZmqFrontend')
    storage = Connector(interface='TablesStorage')
    aomlogic = Connector(interface='AomLogic')
    poimanager = Connector(interface='PoiManagerLogic')

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)

    def on_activate(self):
        # get hold of a handle to optimizer_logic, load if necessary
        # subscribe to key events, emit a message when done
        super().on_activate()
        self.aomlogic().psat_done.connect(self.notify_psat)
        self.aomlogic().psat_done.connect(self._save_psat)

    def on_deactivate(self):
        super().on_deactivate()
        self.aomlogic().psat_done.disconnect(self.notify_psat)

    def handle_take_psat(self, _):
        self.aomlogic().run_psat()

    def handle_emit_psat(self, _):
        self.notify_psat()

    def handle_save_qudi(self, msg: Message):
        if msg.body != '':
            self.aomlogic().save_psat(tag=msg.body)
        else:
            self.aomlogic().save_psat()

    def handle_set_power(self, msg: Message):
        self.aomlogic().set_power(msg.body)

    def handle_get_power(self, msg: Message):
        power = self.aomlogic().get_power()
        self.log.debug("AOM controller power: {} mW".format(power))
        self.reply(msg, body=power)

    def handle_save(self, msg: Message):
        self._save_psat(tag=msg.body)
        self.reply_ok(msg)

    def _save_psat(self, tag=''):
        with self.storage().tables_context() as t:
            poi = self.poimanager().active_poi
            if not tag:
                tag = poi
            path = Psat.node(tag=tag, timestamp=get_timestamp())
            dataset = t.create_measurement_table(Psat.root, path, Psat.Description)
            dataset.append(list(zip(self.aomlogic().powers, self.aomlogic().psat_data)))
            if poi:
                dataset.attrs['poi'] = poi
            t.flush()
        return dataset

    def notify_psat(self):
        aom = self.aomlogic()
        self.notify('psat_data', body={'powers': aom.powers,
                                       'counts': aom.psat_data})

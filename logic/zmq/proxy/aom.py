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
        self.aomlogic().psat_saved.connect(self.notify_psat_saved)
        self.aomlogic().psat_fit_updated.connect(self.notify_psat_fitted)

    def on_deactivate(self):
        super().on_deactivate()
        self.aomlogic().psat_done.disconnect(self.notify_psat)
        self.aomlogic().psat_saved.disconnect(self.notify_psat_saved)
        self.aomlofic().psat_fit_updated.disconnect(self.notify_psat_fitted)

    def handle_take_psat(self, _):
        self.aomlogic().run_psat()

    def handle_emit_psat(self, _):
        self.notify_psat()

    def handle_set_power(self, msg: Message):
        self.aomlogic().set_power(msg.body)

    def handle_get_power(self, msg: Message):
        power = self.aomlogic().get_power()
        self.log.debug("AOM controller power: {} mW".format(power))
        self.reply(msg, body=power)

    def handle_save_psat_hdf5(self, msg: Message):
        poi = self.poimanager().active_poi
        roi = self.poimanager().roi_name
        tag = msg.body.get("tag", poi)
        powers = self.aomlogic().powers
        psat_data = self.aomlogic().psat_data
        data = Psat(poi=poi, roi=roi, tag=tag, power=powers, count_rate=psat_data)
        path = data.store(self.storage().tables_context())
        self.reply(msg, {'file': self.storage().local_filepath, 'path': path})

    def handle_save_psat_qudi(self, msg:Message):
        tag = msg.body.get('tag', '')
        self.aomlogic().save_psat(tag=tag)

    def notify_psat(self):
        aom = self.aomlogic()
        self.notify('psat.data', body={'powers': aom.powers, 'counts': aom.psat_data})

    def notify_psat_saved(self, path=''):
        self.notify('psat.saved', body={'path': path})

    def notify_psat_fitted(self):
        fitted_Isat = self.aomlogic().fitted_Isat
        fitted_Psat = self.aomlogic().fitted_Psat
        fitted_bg = self.aomlogic().fitted_offset
        self.notify('psat.fitted', body={'Isat': fitted_Isat, 'Psat': fitted_Psat, 'bg': fitted_bg})
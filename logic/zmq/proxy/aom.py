from . base import ZmqProxy
from core.connector import Connector
from logic.zmq.message import Message
from logic.zmq.data.psat import Psat


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
        self.aomlogic().psat_fit_updated.connect(self.notify_psat_fitted)

    def on_deactivate(self):
        super().on_deactivate()
        self.aomlogic().psat_done.disconnect(self.notify_psat)
        self.aomlogic().psat_fit_updated.disconnect(self.notify_psat_fitted)

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

    def handle_save_hdf5(self, msg: Message):
        poi = self.poimanager().active_poi
        roi = self.poimanager().roi_name
        tag = msg.body.get("tag", poi)
        powers = self.aomlogic().powers
        psat_data = self.aomlogic().psat_data
        data = Psat(poi=poi, roi=roi, tag=tag, power=powers, count_rate=psat_data)
        location = data.store(self.storage().tables_context())
        self.notify_hdf5_saved(location)
        self.reply(msg, body=location)

    def handle_save_qudi(self, msg: Message):
        tag = msg.body.get('tag', '')
        location = self.aomlogic().save_psat(tag=tag)
        self.reply(msg, body=location)

    def notify_psat(self):
        aom = self.aomlogic()
        self.notify('psat.data', body={'powers': aom.powers, 'counts': aom.psat_data})

    def notify_hdf5_saved(self, location):
        self.notify('psat.hdf5_saved', body=location)

    def notify_psat_fitted(self, Isat: float, Psat: float, bg: float):
        if not (Isat == 0.0 and Psat == 0.0 and bg == 0.0):
            self.log.debug("Psat fitted: Isat({}) Psat({}) bg({})".format(Isat, Psat, bg))
            self.notify('psat.fitted', body={'Isat': Isat, 'Psat': Psat, 'bg': bg})

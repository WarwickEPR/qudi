from . base import ZmqProxy
from core.connector import Connector
from logic.zmq.message import Message
from PyQt5.QtCore import Qt
from logic.zmq.data.roi import ROI
import numpy as np
from .. data.tables_context import TablesContext
from .. data.timestamp import get_timestamp


class RoiProxy(ZmqProxy):

    frontend = Connector(interface='ZmqFrontend')
    storage = Connector(interface='TablesStorage')
    poimanager = Connector(interface='PoiManagerLogic')
    optimizer = Connector(interface='OptimizerLogic', optional=True)
    confocal = Connector(interface='ConfocalLogic', optional=True)

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)

    def on_activate(self):
        # get hold of a handle to optimizer_logic, load if necessary
        # subscribe to key events, emit a message when done
        super().on_activate()
        self.poimanager().sigRefocusStateUpdated.connect(self.notify_refocused, Qt.QueuedConnection)

    def on_deactivate(self):
        super().on_deactivate()

    def handle_add_pois(self, msg: Message):
        self.log.debug("Adding POIs")
        pois = [(poi, np.array(p).astype(float)) for poi, p in msg.body]
        for poi, p in pois[:-1]:
            self.poimanager().add_poi(name=poi, position=p, emit_change=False)
        poi, p = pois[-1]
        self.poimanager().add_poi(name=poi, position=p, emit_change=True)
        self.reply_ok(msg)

    def handle_list_pois(self, msg: Message):
        self.log.debug("Listing POIs")
        pois = list(self.poimanager().poi_positions.items())
        self.reply(msg, pois)

    def handle_poi_dict(self, msg: Message):
        self.log.debug("Fetching POI dict")
        pois = self.poimanager().poi_positions
        self.reply(msg, pois)

    def handle_goto_poi(self, msg: Message):
        self.poimanager().go_to_poi(name=msg.body)

    def handle_set_active_poi(self, msg: Message):
        self.poimanager().active_poi = msg.body

    def handle_optimize_poi(self, msg: Message):
        name = msg.body['name']
        update = msg.body.get('update', True)
        self.poimanager().optimise_poi_position(name=name, update_roi_position=update)

    def handle_save_roi(self, msg: Message):
        if msg.body and 'name' in msg.body:
            name = msg.body['name']
            if name is not None:
                self.poimanager().roi_name = name

        name = self.poimanager().roi_name
        self.log.debug("Saving ROI {}".format(name))

        # HDF5 save
        if self.storage().attached():
            tc: TablesContext = self.storage().tables_context()
            with tc as th:
                group = '{}/{}'.format(ROI.root, name)
                pois_node = 'pois_{}'.format(get_timestamp())
                data_type = ROI.version
                t = th.tables.create_table(group, pois_node, description=ROI.Description, createparents=True)
                if self.poimanager().poi_names:
                    positions = [(k, *v) for (k, v) in self.poimanager().poi_positions.items()]
                    t.append(positions)
                attrs = {'data_type': data_type,
                         'origin': self.poimanager().roi_origin}
                for (k, v) in attrs.items():
                    t.attrs[k] = v
                th.flush()
                self.reply(msg, t._v_pathname)
        else:
            self.reply(msg, '')

    def handle_reset_roi(self, msg: Message):
        self.log.debug("Resetting ROI")
        self.poimanager().reset_roi()
        if msg.body and 'name' in msg.body:
            self.poimanager().roi_name = msg.body['name']
        self.reply_ok(msg)

    def handle_start_tracking(self, msg: Message):
        self.log.debug("Starting tracking periodically")
        self.poimanager().toggle_periodic_refocus(True)
        self.reply_ok(msg)

    def handle_stop_tracking(self, msg: Message):
        self.log.debug("Stopping tracking")
        self.poimanager().toggle_periodic_refocus(False)
        self.reply_ok(msg)

    def notify_refocused(self, running):
        if not running:
            # finished refocus
            self.notify(topic='reoptimized', body={})

    # def handle_initialise_registration(self, msg: Message):
    #     try:
    #         x0 = msg.body['x0']
    #         x1 = msg.body['x1']
    #         y0 = msg.body['y0']
    #         y1 = msg.body['y1']
    #         z0 = msg.body['z0']
    #         z1 = msg.body['z1']
    #
    #         self.xy_ref = self._take_xy_registration()
    #         self.xz_ref = self._take_depth_registration()
    #
    # def _take_xy_registration(self):
    #     self.confocal().scan_xy()
    #     self.confocal().history_back()
    #     return []
    #
    # def _take_depth_registration(self):
    #     self.confocal().scan_depth()
    #     self.confocal().history_back()
    #     return []
    #
    # def handle_correct_wrt_registration(self, msg):
    #     # throw an error if not initialised
    #     current_xy = self._take_xy_registration()
    #     current_xz = self._take_depth_registration()
    #     # use https://scikit-image.org/docs/dev/auto_examples/registration/plot_register_translation.html
    #     # to track shift in both axes. If less than some threshold, update the POI anchor accordingly and update the
    #     # reference images? At least update the correction to the image positions.
from . base import ZmqProxy
from core.connector import Connector
from logic.zmq.message import PubMessage, Message
import numpy as np
from .. data.optimizer import OptimizerTrack, OptimizerImage

class OptimizerProxy(ZmqProxy):

    frontend = Connector(interface='ZmqFrontend')
    storage = Connector(interface='TablesStorage')
    optimizer = Connector(interface='OptimizerLogic')
    poimanager = Connector(interface='PoiManagerLogic')
    scanner = Connector(interface='ConfocalLogic')

    attributes = {'status_vars': '_statusVariables',
                  'xy_size': 'refocus_XY_size',
                  'xy_res': 'optimizer_XY_res',
                  'z_size': 'refocus_Z_size',
                  'z_res': 'optimizer_Z_res'}

    data_fields = {'xy_counts': 'xy_refocus_image',
                   'z_counts': 'z_refocus_line',
                   'z_position': '_zimage_Z_values',
                   'z_fit_position': '_fit_zimage_Z_values',
                   'z_fit': 'z_fit_data',
                   'x': 'optim_pos_x',
                   'x_sigma': 'optim_sigma_x',
                   'y': 'optim_pos_y',
                   'y_sigma': 'optim_sigma_y',
                   'z': 'optim_pos_z',
                   'z_sigma': 'optim_sigma_z'}

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)
        self.poi = None
        self._initial_poi = None
        self._save_on_refocus = False

    def on_activate(self):
        # get hold of a handle to optimizer_logic, load if necessary
        # subscribe to key events, emit a message when done
        super().on_activate()
        self.optimizer().sigRefocusFinished.connect(self._refocused)
        self.poimanager().sigRefocusStateUpdated.connect(self._poi_refocusing)

    def on_deactivate(self):
        self.optimizer().sigRefocusFinished.disconnect(self._refocused)
        self.poimanager().sigRefocusStateUpdated.disconnect(self._poi_refocusing)
        super().on_deactivate()

    def handle_refocus(self, msg: Message):
        # call optimizer to start refocus
        self.log.debug("Starting refocus")
        if 'poi' in msg.body:
            self._initial_poi = msg.body['poi']
            self.optimizer().start_refocus(caller_tag="zmq", initial_pos=self._initial_poi)
        else:
            self.optimizer().start_refocus(caller_tag="zmq")

    def handle_save_on_refocus(self, msg: Message):
        self._save_on_refocus = msg.body

    def handle_setup(self, msg: Message):
        xy_change = False
        z_change = False
        if 'xy_span' in msg.body:
            self.optimizer().refocus_XY_size = float(msg.body['xy_span'])
            xy_change = True
        if 'xy_resolution' in msg.body:
            self.optimizer().optimizer_XY_res = float(msg.body['xy_resolution'])
            xy_change = True
        if 'z_span' in msg.body:
            self.optimizer().refocus_Z_size = float(msg.body['z_span'])
            z_change = True
        if 'z_resolution' in msg.body:
            self.optimizer().optimizer_Z_res = float(msg.body['z_resolution'])
            z_change = True

        if xy_change:
            self.optimizer().sigRefocusXySizeChanged.emit()

        if z_change:
            self.optimizer().sigRefocusZSizeChanged.emit()

    def handle_save_hdf5(self, msg: Message):
        path = self.save_data()
        location = {'file': self.storage().local_filepath, 'path': path}
        self.reply(msg, location)
        self.notify_saved_hdf5(location)

    def notify_saved_hdf5(self, location):
        self.notify('optimizer.saved_hdf5', location)

    def save_data(self):
        attr = {}
        for a, b in self.data_fields.items():
            try:
                v = getattr(self.optimizer(), b)
                attr[a] = v
            except AttributeError as e:
                pass

        with self.storage().tables_context() as t:
            group = t.create_group('Optimizer', poi=self.poi)
            group.attrs.update(attr)
            dataset_XY = t.tables.create_array(group, 'XY', self.optimizer().xy_refocus_image)
            z = self.optimizer()._zimage_Z_values
            z_data = self.optimizer().z_refocus_line
            dataset_Z = t.tables.create_array(group, 'Z', np.array([z, z_data]).transpose())
            return group._v_pathname

    def handle_goto_current(self, _):
        x = self.optimizer().optim_pos_x
        y = self.optimizer().optim_pos_y
        z = self.optimizer().optim_pos_z
        self.scanner().set_position('zmq', x=x, y=y, z=z)

    def emit_refocused(self):
        self.notify(topic='refocused', body=position)

    def _refocused(self, caller_tag, position):
        self.emit_refocused()
        if self._save_on_refocus:
            self.save_hdf5()

    def save_hdf5(self, tag=''):
        fit = {'x': self.optimizer().optim_pos_x,
               'y': self.optimizer().optim_pos_y,
               'z': self.optimizer().optim_pos_z,
               'sigma_x': self.optimizer().optim_sigma_x,
               'sigma_y': self.optimizer().optim_sigma_y,
               'sigma_z': self.optimizer().optim_sigma_z}
        setup = {'xy_resolution': self.optimizer().optimzer_XY_res,
                 'z_resolution': self.optimizer().optimizer_Z_res,
                 'xy_span': self.optimizer().refocus_XY_size,
                 'z_span': self.optimizer().refocus_Z_size}
        roi = self.poimanager().roi_name
        poi = self.poimanager().active_poi
        xy_data = self.optimizer().xy_refocus_image
        z_data = self.optimizer().z_refocus_line

        data = OptimizerImage(tag=tag, roi=roi, poi=poi, xy_data=xy_data, z_data=z_data, setup=setup, fit=fit)
        OptimizerTrack.record_refocus(self.storage().tables_context(), data)

    def _check_on_poi(self, poi):
        # if optimizing from POI manager, may be on a poi
        if poi:
            p = self.poimanager().get_poi_position(poi)
            current = self.scanner().get_position()
            if p is None:
                return False
            d = np.linalg.norm(current - p)
            if d < self.optimizer().refocus_XY_size / 2:
                # looks like this is still on this poi
                return True
            else:
                return False
        else:
            return False

    def _poi_refocusing(self, in_progress):
        active_poi = self.poimanager().active_poi
        if in_progress:
            # starting refocus
            if self._initial_poi:
                self.poi = self._initial_poi
            elif active_poi:
                # have we come from poimanager?
                if self._check_on_poi(active_poi):
                    # starting a refocus, on active_poi
                    self.poi = active_poi
            else:
                self.poi = None
        else:
            # finished refocus
            self._initial_poi = None
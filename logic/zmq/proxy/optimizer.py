from numpy.lib.recfunctions import unstructured_to_structured

from . base import ZmqProxy
from core.connector import Connector
from logic.zmq.message import PubMessage, Message
import numpy as np
from .. data.optimizer import OptimizerTrack, OptimizerImage
from ..data.tables_context import TablesContext


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
        self._autosave_on_refocus = False

    def on_activate(self):
        # get hold of a handle to optimizer_logic, load if necessary
        # subscribe to key events, emit a message when done
        super().on_activate()
        self.optimizer().sigRefocusFinished.connect(self._refocused)

    def on_deactivate(self):
        self.optimizer().sigRefocusFinished.disconnect(self._refocused)
        super().on_deactivate()

    def handle_refocus(self, msg: Message):
        # call optimizer to start refocus
        self.log.info("Starting refocus")
        if 'poi' in msg.body:
            self._initial_poi = msg.body['poi']
            self.optimizer().start_refocus(caller_tag="zmq", initial_pos=self._initial_poi)
        else:
            self.optimizer().start_refocus(caller_tag="zmq")

    def handle_stop(self, _):
        self.log.info("Stopping refocus")
        self.optimizer().stop_refocus()

    def handle_autosave_on_refocus(self, msg: Message):
        state = msg.body
        self.log.info("Setting refocus autosave: {}".format('on' if state else 'off'))
        self._autosave_on_refocus = state

    def handle_setup(self, msg: Message):
        xy_change = False
        z_change = False
        self.debug("Changing optimizer settings to: {}".format(msg.body))
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
        filepath, datapath = self.save_hdf5()
        location = {'file': filepath, 'path': datapath}
        self.reply(msg, location)

    def notify_saved_hdf5(self, location):
        self.notify('saved_hdf5', location)

    def _fetch_result(self):
        xy_fitted = self.optimizer().optim_sigma_x != 0 and self.optimizer().optim_sigma_y != 0
        z_fitted = self.optimizer().optim_sigma_z != 0
        x = self.optimizer().optim_pos_x
        y = self.optimizer().optim_pos_y
        z = self.optimizer().optim_pos_z

        # estimated counts from Z fit
        zif = self.optimizer().z_fit_data
        counts = max(zif) - min(zif) if z_fitted else 0

        # check in bounds
        x0 = self.optimizer()._X_values[0]
        x1 = self.optimizer()._X_values[-1]
        y0 = self.optimizer()._Y_values[0]
        y1 = self.optimizer()._Y_values[-1]
        z0 = self.optimizer()._zimage_Z_values[0]
        z1 = self.optimizer()._zimage_Z_values[-1]

        if x0 < x < x1 and y0 < y < y1 and z0 < z < z1:
            in_bounds = True
        else:
            in_bounds = False

        return {'xy_fitted': xy_fitted,
                'z_fitted': z_fitted,
                'fitted_counts': counts,
                'in_bounds': in_bounds,
                'x': x,
                'y': y,
                'z': z}

    def handle_goto_current(self, _):
        p = self._fetch_result()
        x = p['x']
        y = p['y']
        z = p['z']
        if p['xy_fitted'] and p['z_fitted']:
            self.log.info("Setting optimizer position to {:.2f}, {:.2f}, {:.2f} um. Count rate about {}".format(x*1e6, y*1e6, z*1e6, p['fitted_counts']))
            self.scanner().set_position('zmq', x=x, y=y, z=z)
        elif p['xy_fitted']:
            self.scanner().set_position('zmq', x=x, y=y)
            self.log.warn("Z optimizer fit failed, only updated XY")
        else:
            self.log.warn("Not updating position to current as the optimizer fit failed")

    def handle_emit_refocused(self, _):
        self.emit_refocused()

    def emit_refocused(self):
        p = self._fetch_result()
        self.notify(topic='refocused', body=p)

    def _refocused(self, caller_tag, position):
        self.emit_refocused()
        if self._autosave_on_refocus:
            filepath, datapath = self.save_hdf5()

    def save_hdf5(self, tag=''):
        p = self._fetch_result()
        x = p['x']
        y = p['y']
        z = p['z']
        fit = {'x': x, 'y': y, 'z': z,
               'sigma_x': self.optimizer().optim_sigma_x,
               'sigma_y': self.optimizer().optim_sigma_y,
               'sigma_z': self.optimizer().optim_sigma_z,
               'fitted_z_counts': p['fitted_counts'],
               'xy_fitted': p['xy_fitted'],
               'z_fitted': p['z_fitted']}
        setup = {'xy_resolution': self.optimizer().optimizer_XY_res,
                 'z_resolution': self.optimizer().optimizer_Z_res,
                 'xy_span': self.optimizer().refocus_XY_size,
                 'z_span': self.optimizer().refocus_Z_size,
                 'x0': self.optimizer()._X_values[0],
                 'x1': self.optimizer()._X_values[-1],
                 'y0': self.optimizer()._Y_values[0],
                 'y1': self.optimizer()._Y_values[-1]}
        roi = self.poimanager().roi_name
        poi = self.poimanager().active_poi
        xy_data = self.optimizer().xy_refocus_image[:, :, 3]
        z_values = self.optimizer()._zimage_Z_values
        opt_channel = self.optimizer().opt_channel
        z_counts = self.optimizer().z_refocus_line[:, opt_channel]
        z_data = unstructured_to_structured(np.vstack((z_values, z_counts)).T, names=['z', 'counts'])

        tc: TablesContext = self.storage().tables_context()
        data = OptimizerImage(tag=tag, roi=roi, poi=poi, xy_data=xy_data, z_data=z_data, setup=setup, fit=fit)
        OptimizerTrack.record_refocus(tc, data)

        self.log.info("Saving optimizer result to {}:/{}".format(tc.filepath, data.poi_path))
        location = {'file': tc.filepath, 'path': data.poi_path}
        self.notify_saved_hdf5(location)

        return tc.filepath, data.poi_path

from . base import ZmqProxy
from core.connector import Connector
from .. message import Message
from PyQt5.QtCore import Qt
from .. data.image import Orientation
from .. data.tables_context import TablesContext
import numpy as np
from .. data.timestamp import Timestamp

from ..storage import NoDataFileSpecified

# Binds to confocal_logic to get data from imaging and to control imaging under automation


class ConfocalProxy(ZmqProxy):

    frontend = Connector(interface='ZmqFrontend')
    storage = Connector(interface='TablesStorage')
    confocal = Connector(interface='ConfocalLogic')
    scanning_device = Connector(interface='ConfocalScannerInterface')  # physical device, no interfuse

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)
        self._xy_image_timestamp = None
        self._depth_image_timestamp = None
        self._xy_images = []
        self._depth_images = []
        self._x = 0
        self._y = 0
        self._z = 0

    def on_activate(self):
        super().on_activate()
        self.confocal().module_state.sigStateChanged.connect(self._notify_state_change)
        # save every scan started
        self.confocal().sigImageXYInitialized.connect(self._starting_xy_image, Qt.QueuedConnection)
        self.confocal().sigImageDepthInitialized.connect(self._starting_depth_image, Qt.QueuedConnection)
        # scan stopped
        self.confocal().signal_stop_scanning.connect(self._stopping, Qt.QueuedConnection)
        self.confocal().signal_change_position.connect(self._changed_position, Qt.QueuedConnection)

    def on_deactivate(self):
        super().on_deactivate()
        self.confocal().module_state.sigStateChanged.disconnect(self._notify_state_change)
        self.confocal().sigImageXYInitialized.disconnect(self._starting_xy_image)
        self.confocal().sigImageDepthInitialized.disconnect(self._starting_depth_image)
        self.confocal().signal_stop_scanning.disconnect(self._stopping)
        self.confocal().signal_change_position.disconnect(self._changed_position)

    def _get_scanner_position(self):
        p = self.scanning_device().get_scanner_position()
        self._x = x = p[0]
        self._y = y = p[1]
        self._z = z = p[2]
        return x, y, z

    def _set_scanner_position(self, x, y, z, a=None):
        status = self.scanning_device().scanner_set_position(x=x, y=y, z=z, a=a)
        if status == -1:
            # failed
            return False
        else:
            return True

    # For convenience, keep note of the path to latest images saved
    @property
    def latest_xy_image(self):
        return self._xy_images[0] if self._xy_images else None

    @property
    def latest_depth_image(self):
        return self._depth_images[0] if self._depth_images else None

    def _record_xy_image(self, path):
        self._xy_images.insert(0, path)

    def _record_depth_image(self, path):
        self._depth_images.insert(0, path)

    def _notify_state_change(self, e):
        self.notify('state_change')

    # fetch the stage position, not the ambiguous tilted position
    def _changed_position(self, _):
        x, y, z = self._get_scanner_position()
        self.notify('position_changed_to', {'x': x, 'y': y, 'z': z})

    def _notify_scan_stopped(self):
        self.notify('stopped')

    def _starting_xy_image(self):
        self.notify('xy_image_started')

    def _starting_depth_image(self):
        self.notify('depth_image_started')

    def handle_start_scan(self, msg: Message):
        if self.confocal().module_state.current != 'idle':
            # scanner is currently busy
            self.reply(msg, body='Scanner busy')
            return

        orientation = self._setup_scan(msg)
        self._start_scan(orientation)

    def _stopping(self):
        # when a scan is stopped, save it
        if self.confocal()._zscan:
            self._save_depth_image()
        else:
            self._save_xy_image()

    def _setup_scan(self, msg: Message):

        # set the area to scan
        if 'x0' in msg.body: self.confocal().image_x_range[0] = msg.body['x0']
        if 'x1' in msg.body: self.confocal().image_x_range[1] = msg.body['x1']
        if 'y0' in msg.body: self.confocal().image_y_range[0] = msg.body['y0']
        if 'y1' in msg.body: self.confocal().image_y_range[1] = msg.body['y1']
        if 'xy_resolution' in msg.body: self.confocal().xy_resolution = msg.body['xy_resolution']
        if 'orientation' in msg.body:
            orientation = Orientation[msg.body['orientation']]

            # Set scan orientation
            if orientation == Orientation.XZ:
                self.confocal().depth_img_is_xz = True
            elif orientation == Orientation.YZ:
                self.confocal().depth_img_is_yz = False
            return orientation
        else:
            return Orientation.XY

    def _start_scan(self, orientation):

        # Hook into the confocal_logic module's set up to avoid duplicating initialisation
        if orientation == Orientation.XY:
            self.confocal().start_scanning(zscan=False, tag='zmq')
        else:
            self.confocal().start_scanning(zscan=True, tag='zmq')

    def _depth_orientation(self):
        if self.confocal().depth_img_is_xz:
            return Orientation.XZ
        else:
            return Orientation.XY

    def handle_get_position(self, msg: Message):
        x, y, z = self._get_scanner_position()
        self.reply(msg, body=(x, y, z))

    def handle_set_position(self, msg: Message):
        x = y = z = a = None
        if 'x' in msg.body: x = msg.body['x']
        if 'y' in msg.body: y = msg.body['y']
        if 'z' in msg.body: z = msg.body['z']
        if 'a' in msg.body: a = msg.body['a']
        self._set_scanner_position(x, y, z, a)
        self._changed_position(None)  # as we instruct the scanner directly, miss the signal

    def handle_set_tilt(self, msg: Message):
        tilt_x = msg.body.get('tilt_x', 0)
        tilt_y = msg.body.get('tilt_y', 0)
        reference_x = msg.body.get('reference_x', 0)
        reference_y = msg.body.get('reference_y', 0)
        self.confocal()._scanning_device.tilt_variable_ax = tilt_x
        self.confocal()._scanning_device.tilt_variable_ay = tilt_y
        self.confocal()._scanning_device.tilt_reference_x = reference_x
        self.confocal()._scanning_device.tilt_reference_y = reference_y

    def handle_stop(self, _):
        self.confocal().stop_scanning()

    # ask Qudi to save image
    def handle_qudi_save_xy(self, _):
        self.confocal().save_xy_data()

    def handle_qudi_save_depth(self, _):
        self.confocal().save_depth_data()

    # save current XY image to HDF5 session
    def handle_save_xy(self, _):
        self._save_xy_image()

    # save current XY image to HDF5 session
    def handle_save_depth(self, _):
        self._save_depth_image()

    def _notify_xy_image_saved(self, where: str):
        # image saved to .h5
        finished = not self.confocal()._xyscan_continuable
        self.notify('xy_image_saved', body={'file': self.storage().data_file_path,
                                            'where': where,
                                            'complete': finished})

    def _notify_depth_image_saved(self, where: str):
        # image saved to .h5
        finished = not self.confocal()._zscan_continuable
        self.notify('depth_image_saved', body={'file': self.storage().data_file_path,
                                               'where': where,
                                               'complete': finished})

    def _notify_qudi_xy_image_saved(self):
        finished = not self.confocal()._xyscan_continuable
        # unfortunately not easy to find the output file location
        self.notify('qudi_xy_image_saved', body={'complete': finished})

    def _notify_qudi_depth_image_saved(self):
        finished = not self.confocal()._zscan_continuable
        # unfortunately not easy to find the output file location
        self.notify('qudi_depth_image_saved', body={'complete': finished})

    def _save_image(self, image_type: str, image: np.array, attrs: dict):
        cf = self.confocal()
        if hasattr(cf, 'tilt_correction'):
            # Record the Qudi tilt correction params used
            # Suitable for small tilts, imaging scans and (most?) set_position calls have a dz
            # applied effectively pivoting about "tilt_reference"
            # point1,2,3 are used to find the normal to that plane by cross product and yield tilt_slope
            # calc_dz only uses tilt_reference and tilt_variable_ax = tilt_slope_x
            # Useful for interactive imaging and Qudi integration but the bare-bones "arbitraryscan" system
            # is more flexible and transparent
            attrs['tilt_correction'] = cf.tilt_correction
            attrs['tilt_reference'] = [cf.tilt_reference_x, cf.tilt_reference_y]
            attrs['tilt_slope'] = [cf.tilt_slope_x, cf.tilt_slope_y]

        if self.storage().attached():
            tc: TablesContext = self.storage().tables_context()
            with tc as th:
                group = '/Confocal/' + image_type
                image_name = '{0}_{1}'.format(image_type, Timestamp.get_timestamp())
                data_type = 'Image_{}_v1.0'.format(image_type)
                self.log.debug('Saving image to {} {}/{}'.format(self.storage().data_file_path, group, image_name))
                node = th.create_array(group, image_name, image, data_type)
                for (k, v) in attrs.items():
                    node.attrs[k] = v
                th.flush()
                return node._v_pathname
        else:
            return None

    def _save_xy_image(self):
        cf = self.confocal()
        x_points, y_points, d_points = cf.xy_image.shape
        z_points = 1
        image = np.reshape(cf.xy_image, (x_points, y_points, z_points, d_points))
        attrs = dict()

        # copy everything serialize uses into attributes
        position = self._get_scanner_position()
        x, y, z = position
        attrs['x_range_start'] = cf.image_x_range[0]
        attrs['x_range_end'] = cf.image_x_range[1]
        attrs['x_points'] = x_points
        attrs['y_range_start'] = cf.image_y_range[0]
        attrs['y_range_end'] = cf.image_y_range[1]
        attrs['y_points'] = y_points
        attrs['z_range_start'] = z
        attrs['z_range_end'] = z
        attrs['z_points'] = z_points
        attrs['xy_resolution'] = cf.xy_resolution

        new_node_path = self._save_image('XY', image, attrs)
        if new_node_path:
            self._notify_xy_image_saved(new_node_path)
        return new_node_path

    def _save_depth_image(self):
        cf = self.confocal()

        h_points, z_points, d_points = cf.depth_image.shape
        position = self._get_scanner_position()
        x, y, z = position

        if cf.depth_img_is_xz:
            x_points = h_points
            y_points = 1
            x_range = cf.image_x_range
            y_range = [y, y]
            image_type = 'XZ'
        else:
            x_points = 1
            y_points = h_points
            x_range = [x, x]
            y_range = cf.image_y_range
            image_type = 'YZ'

        image = np.reshape(cf.depth_image, (x_points, y_points, z_points, d_points))
        z_range = cf.image_z_range
        attrs = dict()

        # copy everything serialize uses into attributes
        attrs['position'] = position
        attrs['x_range_start'] = x_range[0]
        attrs['x_range_end'] = x_range[1]
        attrs['x_points'] = x_points
        attrs['y_range_start'] = y_range[0]
        attrs['y_range_end'] = y_range[1]
        attrs['y_points'] = y_points
        attrs['z_range_start'] = z_range[0]
        attrs['z_range_end'] = z_range[1]
        attrs['z_points'] = z_points
        attrs['xy_resolution'] = cf.xy_resolution

        new_node_path = self._save_image(image_type, image, attrs)
        if new_node_path:
            self._notify_depth_image_saved(new_node_path)
        return new_node_path

from . base import ZmqProxy
from core.connector import Connector
from .. message import Message
from PyQt5.QtCore import Qt
from .. common import Orientation
from contextlib import contextmanager


class ConfocalProxy(ZmqProxy):

    frontend = Connector(interface='ZmqFrontend')
    storage = Connector(interface='TablesStorage')
    confocal = Connector(interface='ConfocalLogic')

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)
        self._xy_image_timestamp = None
        self._depth_image_timestamp = None
        self._xy_images = []
        self._depth_images = []

    def on_activate(self):
        super().on_activate()
        self.confocal().module_state.sigStateChanged.connect(self._notify_state_change)
        # save every scan started
        self.confocal().sigImageXYInitialized.connect(self._starting_xy_image, Qt.QueuedConnection)
        self.confocal().sigImageDepthInitialized.connect(self._starting_depth_image, Qt.QueuedConnection)
        # scan stopped
        self.confocal().signal_stop_scanning.connect(self._stopping, Qt.QueuedConnection)

    def on_deactivate(self):
        super().on_deactivate()
        self.confocal().module_state.sigStateChanged.disconnect(self._notify_state_change)
        self.confocal().sigImageXYInitialized.disconnect(self._starting_xy_image)
        self.confocal().sigImageDepthInitialized.disconnect(self._starting_depth_image)
        self.confocal().signal_stop_scanning.disconnect(self._stopping)

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

    def handle_set_position(self, msg: Message):
        x = y = z = a = None
        if 'x' in msg.body: x = msg.body['x']
        if 'y' in msg.body: y = msg.body['y']
        if 'z' in msg.body: z = msg.body['z']
        if 'a' in msg.body: a = msg.body['a']

        self.confocal().set_position('zmq', x=x, y=y, z=z, a=a)

    def handle_get_position(self, msg: Message):
        position = self.confocal().get_position()
        self.reply(msg, body=position)

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

    def _notify_xy_image_saved(self):
        # image saved to .h5
        finished = not self.confocal()._xyscan_continuable
        self.notify('xy_image_saved', body={'file': self.storage().local_filepath,
                                            'path': self.latest_xy_image,
                                            'complete': finished})

    def _notify_depth_image_saved(self):
        # image saved to .h5
        finished = not self.confocal()._zscan_continuable
        self.notify('depth_image_saved', body={'file': self.storage().local_filepath,
                                               'path': self.latest_depth_image,
                                               'complete': finished})

    def _notify_qudi_xy_image_saved(self):
        finished = not self.confocal()._xyscan_continuable
        # unfortunately not easy to find the output file location
        self.notify('qudi_xy_image_saved', body={'complete': finished})

    def _notify_qudi_depth_image_saved(self):
        finished = not self.confocal()._zscan_continuable
        # unfortunately not easy to find the output file location
        self.notify('qudi_depth_image_saved', body={'complete': finished})

    def _save_xy_image(self):
        with self.storage().tables_context() as t:
            cf = self.confocal()
            dataset = t.create_array('Confocal_XY', cf.xy_image)
            # copy everything serialize uses into attributes
            dataset.attrs.focus_position = cf.get_position()
            dataset.attrs.x_range = list(cf.image_x_range)
            dataset.attrs.y_range = list(cf.image_y_range)
            dataset.attrs.z_range = list(cf.image_z_range)
            dataset.attrs.xy_resolution = cf.xy_resolution
            dataset.attrs.xy_scan_continuable = cf._xyscan_continuable
            dataset.attrs.scan_counter = cf._scan_counter
            if hasattr(cf, 'tilt_correction'):
                dataset.attrs.tilt_correction = cf.tilt_correction
                dataset.attrs.tilt_point1     = list(cf.point1)
                dataset.attrs.tilt_point2     = list(cf.point2)
                dataset.attrs.tilt_point3     = list(cf.point3)
                dataset.attrs.tilt_reference  = [cf.tilt_reference_x, cf.tilt_reference_y]
                dataset.attrs.tilt_slope      = [cf.tilt_slope_x,     cf.tilt_slope_y]
            t.flush()

            # path to dataset
            self._record_xy_image(dataset._v_pathname)
            self._notify_xy_image_saved()
            return dataset._v_pathname

    def _save_depth_image(self):
        with self.storage().tables_context() as t:
            cf = self.confocal()
            dataset = t.create_array('Confocal_Depth', cf.depth_image)
            # copy everything serialize uses into attributes
            dataset.attrs.focus_position = cf.get_position()
            dataset.attrs.x_range = list(cf.image_x_range)
            dataset.attrs.y_range = list(cf.image_y_range)
            dataset.attrs.z_range = list(cf.image_z_range)
            dataset.attrs.xy_resolution = cf.xy_resolution
            dataset.attrs.z_resolution = cf.z_resolution
            dataset.attrs.depth_img_is_xz = cf.depth_img_is_xz
            dataset.attrs.depth_dir_is_xz = cf.depth_scan_dir_is_xz
            dataset.attrs.depth_scan_continuable = cf._zscan_continuable
            dataset.attrs.scan_counter = cf._scan_counter
            if hasattr(cf, 'tilt_correction'):
                dataset.attrs.tilt_correction = cf.tilt_correction
                dataset.attrs.tilt_point1     = list(cf.point1)
                dataset.attrs.tilt_point2     = list(cf.point2)
                dataset.attrs.tilt_point3     = list(cf.point3)
                dataset.attrs.tilt_reference  = [cf.tilt_reference_x, cf.tilt_reference_y]
                dataset.attrs.tilt_slope      = [cf.tilt_slope_x,     cf.tilt_slope_y]
            t.flush()

            # path to dataset
            self._record_depth_image(dataset._v_pathname)
            self._notify_depth_image_saved()
            return dataset._v_pathname

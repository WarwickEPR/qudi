from . base import ZmqProxy
from core.connector import Connector
from .. message import Message
from PyQt5.QtCore import Qt
from .. common import Orientation
from contextlib import contextmanager


class ConfocalProxy(ZmqProxy):

    frontend = Connector(interface='ZmqFrontend')
    storage = Connector(interface='HdfStorage')
    confocal = Connector(interface='ConfocalLogic')

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)
        self._xy_image_timestamp = None
        self._depth_image_timestamp = None
        self._disable_hdf_updates = False

    def on_activate(self):
        super().on_activate()
        self.confocal().module_state.sigStateChanged.connect(self._notify_state_change)
        # just save every scan started
        self.confocal().sigImageXYInitialized.connect(self._setup_xy_image_storage, Qt.QueuedConnection)
        self.confocal().sigImageDepthInitialized.connect(self._setup_depth_image_storage, Qt.QueuedConnection)
        self.confocal().signal_xy_image_updated.connect(self._update_xy_hdf, Qt.QueuedConnection)
        self.confocal().signal_depth_image_updated.connect(self._update_depth_hdf, Qt.QueuedConnection)
        self.confocal().signal_stop_scanning.connect(self._notify_scan_stopped, Qt.QueuedConnection)

    def on_deactivate(self):
        super().on_deactivate()
        self.confocal().module_state.sigStateChanged.disconnect(self._notify_state_change)
        self.confocal().sigImageXYInitialized.disconnect(self._setup_xy_image_storage)
        self.confocal().sigImageDepthInitialized.disconnect(self._setup_depth_image_storage)
        self.confocal().signal_xy_image_updated.disconnect(self._update_xy_hdf)
        self.confocal().signal_depth_image_updated.disconnect(self._update_depth_hdf)
        self.confocal().signal_stop_scanning.disconnect(self._notify_scan_stopped)

    def _notify_state_change(self, e):
        self.notify('state_change')

    def _notify_scan_stopped(self):
        self.notify('stopped')

    def _notify_xy_scan_started(self):
        self.notify('xy_image_started', body={'file': self._xy_image_file,
                                              'timestamp': self._xy_image_timestamp,
                                              'dataset': self._xy_image_path})

    def _notify_depth_scan_started(self):
        self.notify('depth_image_started', body={'file': self._depth_image_file,
                                                 'timestamp': self._depth_image_timestamp,
                                                 'dataset': self._depth_image_path})

    def handle_start_scan(self, msg: Message):
        if self.confocal().module_state.current != 'idle':
            # scanner is currently busy
            self.reply(msg, body='Scanner busy')
            return

        orientation = self._setup_scan(msg)
        self._start_scan(orientation)

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

    def _setup_xy_image_storage(self):

        self._xy_image_timestamp = self.storage().timestamp()
        with self._initialize_image_hdf(self._xy_image_timestamp,
                                        Orientation.XY,
                                        self.confocal().xy_image.shape) as ds:
            self._xy_image_file = ds.file.filename
            self._xy_image_path = ds.name
            xy_resolution = self.confocal().xy_resolution
            ds.attrs['xy_resolution'] = xy_resolution
            x_range = self.confocal().x_range
            y_range = self.confocal().y_range
            width = x_range[1] - x_range[0]
            height = y_range[1] - y_range[0]
            ds.attrs['x0'] = x_range[0]
            ds.attrs['x1'] = x_range[1]
            ds.attrs['y0'] = y_range[0]
            ds.attrs['y1'] = y_range[1]
            ds.attrs['z'] = self.confocal()._current_z
            ds.attrs['x_range'] = width
            ds.attrs['y_range'] = height
            if width >= height:
                ds.attrs['x_range_px'] = xy_resolution
                ds.attrs['y_range_px'] = int(xy_resolution * height / width)
            else:
                ds.attrs['x_range_px'] = int(xy_resolution * width / height)
                ds.attrs['y_range_px'] = xy_resolution

    def _setup_depth_image_storage(self):

        self._depth_image_timestamp = self.storage().timestamp()
        orientation = self._depth_orientation()
        with self._initialize_image_hdf(self._xy_image_timestamp,
                                        orientation,
                                        self.confocal().depth_image.shape) as ds:
            self._depth_image_file = ds.file.filename
            self._depth_image_path = ds.name
            xy_resolution = self.confocal().xy_resolution
            z_resolution = self.confocal().z_resolution
            ds.attrs['xy_resolution'] = xy_resolution
            ds.attrs['z_resolution'] = z_resolution
            z_range = self.confocal().z_range
            if orientation == Orientation.XZ:
                x_range = self.confocal().x_range
                width = x_range[1] - x_range[0]
                ds.attrs['x0'] = x_range[0]
                ds.attrs['x1'] = x_range[1]
                ds.attrs['y'] = self.confocal()._current_y
            else:
                y_range = self.confocal().y_range
                width = y_range[1] - y_range[0]
                ds.attrs['y0'] = y_range[0]
                ds.attrs['y1'] = y_range[1]
                ds.attrs['x'] = self.confocal()._current_x

            height = z_range[1] - z_range[0]
            ds.attrs['z0'] = z_range[0]
            ds.attrs['z1'] = z_range[1]
            ds.attrs['x_range'] = width
            ds.attrs['z_range'] = height

    @contextmanager
    def _initialize_image_hdf(self, timestamp, orientation, dimensions):
        with self.storage().measurement_folder('confocal/' + orientation.name, timestamp=timestamp) as m:
            ds = m.create_dataset('raw', dimensions, compression='gzip')
            ds.attrs['orientation'] = orientation.name
            ds.attrs['clock_frequency'] = self.confocal()._clock_frequency
            ds.attrs['return_slowness'] = self.confocal().return_slowness
            try:
                yield ds
            finally:
                ds.file.close()

    @contextmanager
    def _current_xy_dataset(self):
        with self.storage().measurement_folder('confocal/XY', timestamp=self._xy_image_timestamp) as m:
            ds = m['raw']
            yield ds

    @contextmanager
    def _current_depth_dataset(self):
        with self.storage().measurement_folder('confocal/' + self._depth_orientation().name, timestamp=self._depth_image_timestamp) as m:
            yield m['raw']

    def handle_stop(self, _):
        self.confocal().stop_scanning()

    def handle_save_xy(self, _):
        self.confocal().save_xy_data()

    def handle_save_depth(self, _):
        self.confocal().save_depth_data()

    def _update_xy_hdf(self):
        if self._xy_image_timestamp and not self._disable_hdf_updates:
            try:
                self.log.debug("Updating xy image")
                with self._current_xy_dataset() as ds:
                    ds[...] = self.confocal().xy_image
                #self.notify('xy_image_updated')
            except Exception as e:
                self.log.error("Exception thrown in xy image updates ({}). Halting updates until module restart.".format(e))
                self._disable_hdf_updates = True

    def _update_depth_hdf(self):
        if self._depth_image_timestamp and not self._disable_hdf_updates:
            try:
                self.log.debug("Updating depth image")
                with self._current_depth_dataset() as ds:
                    ds[...] = self.confocal().depth_image
                    # self.notify('depth_image_updated')
            except Exception as e:
                self.log.error("Exception thrown in depth image updates ({}). Halting updates until module restart.".format(e))
                self._disable_hdf_updates = True

    def _notify_xy_image_finished(self):
        self._xy_image_timestamp = None
        self.notify('xy_image', body=self._xy_image_timestamp)

    def _notify_depth_image_finished(self):
        self._depth_image_timestamp = None
        self.notify('depth_image', body=self._depth_image_timestamp)

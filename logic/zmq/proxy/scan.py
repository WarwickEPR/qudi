from . base import ZmqProxy
from core.connector import Connector
from .. message import Message
from PyQt5.QtCore import Qt
from .. common import Orientation
from contextlib import contextmanager


class ScanProxy(ZmqProxy):

    frontend = Connector(interface='ZmqFrontend')
    storage = Connector(interface='HdfStorage')
    scanner = Connector(interface='ScanLogic')

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)

    def on_activate(self):
        super().on_activate()
        self.scanner().sigScanFinished.connect(self._notify_scan_stopped)
        self.scanner().sigScanFinished.connect(self._save_image)

    def on_deactivate(self):
        super().on_deactivate()

    def _notify_scan_stopped(self):
        self.notify('finished')

    def _notify_scan_started(self):
        self.notify('started', body={'file': self._xy_image_file,
                                     'timestamp': self._xy_image_timestamp,
                                     'dataset': self._xy_image_path})

    def handle_start_scan(self, msg: Message):
        if self.scanner().module_state.current != 'idle':
            # scanner is currently busy
            self.reply(msg, body='Scanner busy')
            return

        if 'points' not in msg:
            self.reply(msg, body='No points supplied')
            return

        points = msg['points']
        clock_frequency = msg.get('clock', 100)
        return_speed = msg.get('return_speed', 3e-4)  # defaults to 0.3 mm/s

        self._start_scan(points, clock_frequency=clock_frequency, return_speed=return_speed)
        self.reply(msg, body='OK')

    def _setup_image_storage(self):

        self._image_timestamp = self.storage().timestamp()
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
        with self.storage().folder('confocal/' + orientation.name, timestamp=timestamp) as m:
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
        with self.storage().folder('confocal/XY', timestamp=self._xy_image_timestamp) as m:
            ds = m['raw']
            yield ds

    @contextmanager
    def _current_depth_dataset(self):
        with self.storage().folder('confocal/' + self._depth_orientation().name,
                                   timestamp=self._depth_image_timestamp) as m:
            yield m['raw']

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

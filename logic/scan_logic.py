from qtpy import QtCore
from logic.generic_logic import GenericLogic
from core.connector import Connector
import numpy as np
import itertools


class OutOfBounds(Exception):
    pass


class ScanLogic(GenericLogic):

    """A bare-bones confocal image scanner module. Just captures an image given a list of points.
    Fills in slowed down flyback points
    """

    # declare connectors
    confocal_scanner = Connector(interface='ConfocalScannerInterface')

    _sigStartScan = QtCore.Signal(float, float)
    sigScanStarted = QtCore.Signal()
    _sigStopScan = QtCore.Signal()
    sigScanStopped = QtCore.Signal()
    _sigNextChunk = QtCore.Signal()
    sigScanFinished = QtCore.Signal()

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)

        self._stopRequested = False
        self._scanning_device = None
        self._update_period = 5
        self._pending_points = None
        self._scan_data = None
        self._points = []

    def on_activate(self):
        self._scanning_device = self.confocal_scanner()

        self._sigStartScan.connect(self._start_scan, QtCore.Qt.QueuedConnection)
        self._sigStopScan.connect(self._stop_scan, QtCore.Qt.QueuedConnection)
        self._sigNextChunk.connect(self._scan_next_chunk, QtCore.Qt.QueuedConnection)
        self.sigScanStopped.connect(self._release_scanner)
        self.sigScanFinished.connect(self._release_scanner)

        return 0

    def on_deactivate(self):
        self._sigStartScan.disconnect(self._start_scan)
        self._sigStopScan.disconnect(self._stop_scan)
        self.sigScanStopped.disconnect(self._release_scanner)
        self.sigScanFinished.disconnect(self._release_scanner)

        return 0

    @classmethod
    def distance(cls, a: np.array, b: np.array):
        # where a, b are 3, n arrays of coords of equal length
        # tips on efficient methods gleaned from:
        # https://stackoverflow.com/questions/1401712/how-can-the-euclidean-distance-be-calculated-with-numpy
        return np.sqrt(np.sum((b-a) ** 2, 1))

    @classmethod
    def _interpolate_speed_limit(cls, points: np.array, speed, clock_frequency):
        # with speed limit in m/s, maximum distance per tick
        d_per_tick = speed / clock_frequency

        # calculate the distances between successive points
        points_shifted = np.roll(points, -1, 0)
        d = cls.distance(points, points_shifted)

        # find the number of interpolated steps each takes
        n_steps = np.floor(d / d_per_tick).astype(int)+1

        # work out the steps
        axes = points.shape[1]
        step_fraction = np.reciprocal(n_steps.astype(float)) * np.ones((axes, 1))
        v_between = np.multiply(points_shifted - points, step_fraction.T)

        # Then make a generator for the new list of points with interpolated steps
        scan_steps = zip(points, n_steps, v_between)

        expanded_points = zip(cls._expand_points(scan_steps), cls._wanted_points(range(0, len(points)), n_steps))
        return cls._append_return_point(expanded_points, points[0, :])

    @classmethod
    def _append_return_point(cls, g, p):
        yield from g
        yield p, -1

    @classmethod
    def _expand_points(cls, z):
        for p, n, v in z:
            for i in range(0, n):
                yield p + i * v

    @classmethod
    def _wanted_points(cls, point_index, number_of_steps):
        for i, n in zip(point_index, number_of_steps):
            for step in range(0, n):
                if step == 0:
                    yield i
                else:
                    yield -1

    @classmethod
    def _chunk(cls, points, chunk_size):
        # Return first n items of the iterable as a list
        # taken from itertools documentation
        return list(itertools.islice(points, chunk_size))

    def start_scan(self, points, clock_frequency=100, return_speed=1e-3):
        if not self._check_in_bounds(points):
            self.log.warn("Scan not started. Some points are out of bounds.")
            raise OutOfBounds

        self._pending_points = points
        self._sigStartScan.emit(clock_frequency, return_speed)

    def _stop_scan(self):
        self._stopRequested = True

    def _check_in_bounds(self, points):
        bounds = np.array(self._scanning_device.get_position_range())
        return np.all(np.logical_and(np.greater_equal(points, bounds[:, 0]),
                                     np.less_equal(points, bounds[:, 1])))

    def _release_scanner(self):
        self._scanning_device.close_scanner()
        self._scanning_device.close_scanner_clock()
        if self._scanning_device.module_state.current == 'locked':
            self._scanning_device.module_state.unlock()
        self.module_state.unlock()

    def _start_scan(self, clock_frequency, return_speed):

        # get control of the scanning device
        self.module_state.lock()
        clock_status = self._scanning_device.set_up_scanner_clock(clock_frequency=clock_frequency)
        if clock_status < 0:
            self.module_state.unlock()
            return

        scanner_status = self._scanning_device.set_up_scanner()
        if scanner_status < 0:
            self._scanning_device.close_scanner_clock()
            self.module_state.unlock()
            return

        # Keep the actual points requested. Let the caller reshape into whatever form is needed
        self._points = self._pending_points
        self.log.info("Starting scan of {} points".format(self._points.shape[0]))
        self._number_of_channels = len(self.confocal_scanner().get_scanner_count_channels())
        self._scan_data = np.zeros((len(self._points), self._number_of_channels))
        self._pending_points = None

        # add "flyback" points to slow large movements down
        # use generators to avoid copying around large arrays
        # includes a boolean for which points are actually wanted
        interpolated_points = self._interpolate_speed_limit(self._points, return_speed, clock_frequency)

        # also add "flyback" from current position and back
        route = self._to_and_from(self._scanning_device.get_scanner_position()[0:3], self._points[0, :], interpolated_points, return_speed, clock_frequency)

        # chunk the point list generator so updates can be sent out periodically
        chunk_size = int(self._update_period * clock_frequency)
        self._chunked_points = iter(lambda: self._chunk(route, chunk_size), [])

        # start scanning
        self._sigNextChunk.emit()

    @classmethod
    def _to_and_from(cls, current: np.array, start: np.array, points: np.array, speed_limit, clock_frequency):
        d_per_tick = speed_limit / clock_frequency
        v = start - current
        d = cls.distance(np.array([start]), np.array([current]))[0]
        steps = int(np.floor(d / d_per_tick)+1)
        dv = np.true_divide(v, steps)
        for i in range(1, int(steps)):
            yield current + i * dv, -1
        yield from points
        for i in range(steps, -1, -1):
            yield current + i * dv, -1

    def _scan_next_chunk(self):
        if self._stopRequested:
            self._stopRequested = False
            self.sigScanStopped.emit()
            # stop scanning chunks
            return
        # otherwise, try getting more points to scan
        try:
            chunk = next(self._chunked_points, None)
            if not chunk:
                self.log.debug("Finished iteration")
                self._stopRequested = False
                self.sigScanFinished.emit()
                return
            points = np.array([p for p, _ in chunk])
            wanted = np.array([i for _, i in chunk])

            self.log.debug("Scanning chunk {}".format(points))
            # scan this list of points and throw away the ones we don't need
            scan_line_points = points.T
            self.log.debug("Scan line input shape: {} {}".format(scan_line_points.shape, scan_line_points))
            data = self._scanning_device.scan_line(scan_line_points)
            self.wanted = wanted
            self.data = data
            wanted_counts = list(itertools.filterfalse(lambda t: t[1] < 0, zip(data, wanted)))
            self.wanted_counts = wanted_counts
            #counts = list(((i, cts) for cts, i in zip(data.T, wanted) if i >= 0))
            self.log.debug("returned_counts {}".format(data))
            self.log.debug("wanted {}".format(wanted))
            self.log.debug("counts {}".format(wanted_counts))
            self.log.debug("Acquired {} points, {} wanted".format(len(data), len(wanted_counts)))
            if wanted_counts:
                # save the ones we actually want to the index we passed through
                # conveniently, put_along_axis does just the right thing in one call
                indices = np.array([[i] for _, i in wanted_counts]).astype(int)
                count_data = np.array([cts for cts, _ in wanted_counts])
                self.log.debug("I: {} D: {}".format(indices.shape, count_data.shape))
                np.put_along_axis(self._scan_data, indices, count_data, 0)
        except StopIteration:
            self.log.debug("Finished iteration")
            self._stopRequested = False
            self.sigScanFinished.emit()
            return

        self._sigNextChunk.emit()

    def _scan_line_format(self, points):
        # points is an array in form [n][axes]
        # scan line needs it in the form [px py pz][channels]
        # i.e. with a third dimension of [0:n_ch]
        pass

    def scan_data(self):
        return self._scan_data.T

    # Accept any list of points to permit e.g. distortion compensation, arbitrary orientation scans, volume
    # scans and generally separate the scanning process from how the resulting data is interpreted and used
    # don't integrate with history, GUI etc directly. Just acquire generic scans and let the caller reshape & use them.

    # Provide helper functions to assist. Just include the required points, "flyback" will be handled to limit speed
    # @classmethod
    # def generate_centred_rectangular_path(cls, centre, theta, phi,  width, height, width_px, height_px):
    #     # given centre, angle to 'x,y' directions and with extent of width x height
    #     u = np.array([[1, 0, 0], [0, 1, 0]])
    #
    #     return []

    @classmethod
    def generate_parallelogram_path_from_corners(cls, o: np.array, a: np.array, b: np.array, a_x, b_x):
        # Takes three points to form sides oa and ob. Scan in lines going in one direction, raster scanned
        v_a = np.array(a - o) / (a_x - 1)
        v_b = np.array(b - o) / (b_x - 1)

        # set up for automatic broadcasting by using an array of [x]
        x = np.array([i * v_a for i in range(0, a_x)])
        y = np.array([[j*v_b] for j in range(0, b_x)])
        # use broadcasting to add all combinations of A[i] B[j]

        return np.reshape(o + x + y, (a_x * b_x, len(o)))

    @classmethod
    def generate_xy_path(cls, x_min, x_max, y_min, y_max, z, width_px, height_px):
        a = np.array([x_min, y_min, z])
        b = np.array([x_max, y_min, z])
        c = np.array([x_min, y_max, z])
        return cls.generate_parallelogram_path_from_corners(a, b, c, width_px, height_px)

    @classmethod
    def generate_xz_path(cls, x_min, x_max, y, z_min, z_max, width_px, height_px):
        a = np.array([x_min, y, z_min])
        b = np.array([x_max, y, z_min])
        c = np.array([x_min, y, z_max])
        return cls.generate_parallelogram_path_from_corners(a, b, c, width_px, height_px)

    @classmethod
    def generate_yz_path(cls, x, y_min, y_max, z_min, z_max, width_px, height_px):
        a = np.array([x, y_min, z_min])
        b = np.array([x, y_max, z_min])
        c = np.array([x, y_min, z_max])
        return cls.generate_parallelogram_path_from_corners(a, b, c, width_px, height_px)

    @classmethod
    def generate_parallelepiped_path_from_corners(cls, o: np.array, a: np.array, b: np.array, c: np.array,
                                                  a_px: int, b_px: int, c_px: int):

        # Takes four points to form sides oa, ob and oc. Scan lines going in one direction, raster scanned
        v_a = np.array(a - o) / (a_px - 1)
        v_b = np.array(b - o) / (b_px - 1)
        v_c = np.array(c - o) / (c_px - 1)

        # set up for automatic broadcasting by using an array of [x]
        p_a = np.array([i*v_a     for i in range(0, a_px)])
        p_b = np.array([[j*v_b]   for j in range(0, b_px)])
        p_c = np.array([[[k*v_c]] for k in range(0, c_px)])

        # use broadcasting to add all combinations of A[i] B[j] C[k]
        # order of scanning fastest to slowest is oa, ob, oc
        return np.reshape(o + p_a + p_b + p_c, (a_px * b_px * c_px, len(o)))

    @classmethod
    def generate_xyz_path(cls, x_min, x_max, y_min, y_max, z_min, z_max, x_px, y_px, z_px):
        o = np.array([x_min, y_min, z_min])
        a = np.array([x_min, y_min, z_max])
        b = np.array([x_max, y_min, z_min])
        c = np.array([x_min, y_max, z_min])
        return cls.generate_parallelepiped_path_from_corners(o, a, b, c, x_px, y_px, z_px)

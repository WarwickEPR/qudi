from qtpy import QtCore
from logic.generic_logic import GenericLogic
from core.connector import Connector
import numpy as np
from itertools import tee, count, chain, starmap, filterfalse
from more_itertools import pairwise, chunked
from logic.scan_patterns.general_scan import ArbitraryScan


class OutOfBounds(Exception):
    pass


class ArbitraryScanLogic(GenericLogic):

    """A bare-bones confocal image scanner module. Just captures an image given an iterator of points.
    Fills in slowed down flyback points
    """

    # declare connectors
    confocal_scanner = Connector(interface='ConfocalScannerInterface')

    _sigStartScan = QtCore.Signal()
    sigScanStarted = QtCore.Signal()
    _sigStopScan = QtCore.Signal()
    sigScanStopped = QtCore.Signal()
    _sigNextChunk = QtCore.Signal()
    sigScanFinished = QtCore.Signal()
    sigNewData = QtCore.Signal()

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)

        self._stopRequested = False
        self._scanning_device = None
        self._update_period = 5
        self._scan = None
        self._clock_frequency = 100
        self._return_speed = 0.01

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
#        self.sigScanFinished.disconnect(self._release_scanner)
        return 0

    @classmethod
    def distance(cls, a: np.array, b: np.array):
        return np.sqrt(np.sum((b-a) ** 2))

    @classmethod
    def _interpolate_points(cls, points, starting_position, final_position, speed, clock_frequency):
        # with speed limit in m/s, maximum distance per tick
        d_per_tick = speed / clock_frequency

        # Add journey to and from the scan before interpolation of flyback points
        points1, points2 = tee(points)
        points_with_return = chain([starting_position], points1, [final_position])
        i_points_with_return = chain([(-1, starting_position)],
                                     zip(count(), points2),
                                     [(-1, final_position)])


        # calculate the distances between successive points
        pwr1, pwr2 = tee(points_with_return)
        distance_between_points = starmap(cls.distance, pairwise(pwr1))
        # and hence the number of interpolated steps needed to restrict stage speed
        n_steps = map(lambda d: np.floor(d / d_per_tick).astype(int)+1, distance_between_points)

        # calculate vectors between points
        v = starmap(lambda a, b: b-a, pairwise(pwr2))

        # put it all together and label the points we don't need with -1
        for point, n, v in zip(i_points_with_return, n_steps, v):
            index, p = point
            yield index, p
            s = 1.0/n
            for i in range(1, n):
                yield -1, p + i * s * v

    def start_scan(self, scan: ArbitraryScan, clock_frequency=100, return_speed=1e-2):
        if not self._check_in_bounds(scan):
            self.log.warn("Scan not started. Some points are out of bounds.")
            raise OutOfBounds

        if self.module_state() == 'locked' or self._scanning_device.module_state() == 'locked':
            return -1
        else:
            self._scan = scan
            self._clock_frequency = clock_frequency
            self._return_speed = return_speed
            self._sigStartScan.emit()
            return 0

    def _stop_scan(self):
        self._stopRequested = True

    def _check_in_bounds(self, scan):
        bounds = np.array(self._scanning_device.get_position_range())
        for p in scan.extremal_points():
            if np.logical_or(np.any(np.less(p, bounds[:, 0])), np.any(np.greater(p, bounds[:, 1]))):
                return False
        return True

    def _release_scanner(self):
        self._scanning_device.close_scanner()
        self._scanning_device.close_scanner_clock()
        if self._scanning_device.module_state.current == 'locked':
            self._scanning_device.module_state.unlock()
        self.module_state.unlock()

    def _start_scan(self):

        # get control of the scanning device
        self.module_state.lock()
        clock_status = self._scanning_device.set_up_scanner_clock(clock_frequency=self._clock_frequency)
        if clock_status < 0:
            self.module_state.unlock()
            return

        scanner_status = self._scanning_device.set_up_scanner()
        if scanner_status < 0:
            self._scanning_device.close_scanner_clock()
            self.module_state.unlock()
            return

        # Keep the actual points requested. Let the caller reshape into whatever form is needed
        self.log.info("Starting scan of {} points".format(self._scan.length()))

        # add "flyback" points to slow large movements down
        # use generators to avoid copying around large arrays
        # includes a boolean for which points are actually wanted
        current_position = np.array(self._scanning_device.get_scanner_position()[0:3])
        interpolated_points = self._interpolate_points(self._scan.points(),
                                                       current_position, current_position,
                                                       self._return_speed, self._clock_frequency)

        # chunk the point list generator so updates can be sent out periodically
        chunk_size = int(self._update_period * self._clock_frequency)
        self._chunked_points = chunked(interpolated_points, chunk_size)

        # start scanning
        self._sigNextChunk.emit()

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
            points = np.array([p for _, p in chunk])
            indices = np.array([i for i, _ in chunk])

            self.log.debug("Scanning chunk of {} points".format(len(points)))
            # scan this list of points and throw away the ones we don't need
            scan_line_points = points.T
            data = self._scanning_device.scan_line(scan_line_points)
            wanted_counts = list(filterfalse(lambda t: t[1] < 0, zip(data, indices)))
            wanted_n = len(wanted_counts)
            flyback_n = len(data) - wanted_n

            if wanted_counts:
                # save the ones we actually want to the index we passed through
                # conveniently, put_along_axis does just the right thing in one call
                indices = np.array([[i] for _, i in wanted_counts]).astype(int)
                count_data = np.array([cts for cts, _ in wanted_counts])
                self.log.debug("Avg {} c/s from {} points with {} interpolated to restrict speed".
                               format(np.mean(count_data), wanted_n, flyback_n))
                self._scan.record(indices, count_data)
        except StopIteration:
            self.log.debug("Finished iteration")
            self._stopRequested = False
            self.sigScanFinished.emit()
            return

        self.sigNewData.emit()
        self._sigNextChunk.emit()

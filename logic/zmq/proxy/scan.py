from . base import ZmqProxy
from core.connector import Connector
import logic.scan_patterns.hdf5_scan as scan

from .. message import Message
from contextlib import contextmanager


class ScanProxy(ZmqProxy):

    frontend = Connector(interface='ZmqFrontend')
    storage = Connector(interface='TablesStorage')
    arbscan = Connector(interface='ArbitraryScanLogic')

    def __init__(self, config, **kwargs):
        super(ScanProxy, self).__init__(config=config, **kwargs)
        self._scan = None

    def on_activate(self):
        super().on_activate()
        self.arbscan().sigNewData.connect(self._new_data)
        self.arbscan().sigScanFinished.connect(self._scan_finished)

    def on_deactivate(self):
        super().on_deactivate()
        self.arbscan().sigNewData.disconnect()
        self.arbscan().sigScanFinished.disconnect()

    def _new_data(self):
        if self._scan:
            self._scan.flush()
            self.notify('scan.update', body={'done': self._scan.done()})

    def _scan_finished(self):
        if self._scan:
            self._scan.flush()
            self.notify('scan.finished')

    def handle_start_parallelepiped_scan(self, m: Message):
        try:
            origin = m.body['origin']
            a = m.body['a']
            b = m.body['b']
            c = m.body['c']
            a_px = m.body['points_a']
            b_px = m.body['points_b']
            c_px = m.body['points_c']
        except KeyError as e:
            # missing key
            self.log.warning("Missing key starting pp scan#: {}".format(e))
            return

        return_speed = m.body.get('return_speed', 1e-3)
        clock_frequency = m.body.get('clock_frequency', 100)

        self.log.info("Starting parallelepiped scan over {} points".format(a_px*b_px*c_px))
        self._scan = scan.ParallelepipedScan(self.storage().tables_context(), origin, a, b, c, a_px, b_px, c_px)
        self.arbscan().start_scan(self._scan, clock_frequency=clock_frequency, return_speed=return_speed)

    def handle_start_parallelogram_scan(self, m: Message):
        try:
            origin = m.body['origin']
            a = m.body['a']
            b = m.body['b']
            a_px = m.body['points_a']
            b_px = m.body['points_b']
        except KeyError as e:
            # missing key
            self.log.warning("Missing key starting pg scan#: {}".format(e))
            return

        return_speed = m.body.get('return_speed', 1e-3)
        clock_frequency = m.body.get('clock_frequency', 100)

        self.log.info("Starting parallelogram scan over {} points".format(a_px*b_px))
        self._scan = scan.ParallelogramScan(self.storage().tables_context(), origin, a, b, a_px, b_px)
        self.arbscan().start_scan(self._scan, clock_frequency=clock_frequency, return_speed=return_speed)

    def handle_stop(self, m: Message):
        self.log.info("Stopping scan")
        self.arbscan().stop()

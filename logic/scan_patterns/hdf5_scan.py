from abc import ABC, abstractmethod
import numpy as np
from logic.zmq.data.tables_context import TablesContext
import logic.scan_patterns.general_scan as scan
from queue import Queue
from tables.atom import Float64Atom


# not the most efficient way but the flat iterator doesn't seem to be fully implemented for tables.Array as ndarray
def write_to_h5array_3d(target, indices, data):
    for i, j, d, c in zip(*np.unravel_index(indices, shape=target.shape), data):
        target[i, j, 1, d] = c


def write_to_h5array_4d(target, indices, data):
    for i, j, k, d, c in zip(*np.unravel_index(indices, shape=target.shape), data):
        target[i, j, k, d] = c


class ParallelepipedScan(scan.ParallelepipedScan):

    def __init__(self,
                 tc: TablesContext,
                 o: np.array,
                 a: np.array,
                 b: np.array,
                 c: np.array,
                 a_px: int,
                 b_px: int,
                 c_px: int,
                 data_dim=1):
        self._tc = tc
        self._queue = Queue()
        super(ParallelepipedScan, self).__init__(o, a, b, c, a_px, b_px, c_px, data_dim)

    def initialise_data(self):
        with self._tc as th:
            ts = self._tc.timestamp()
            name = 'ABC_{}'.format(ts)
            arr = th.tables.create_array("/Confocal/ABC",
                                         name,
                                         createparents=True,
                                         atom=Float64Atom(),
                                         shape=(self.points_a, self.points_b, self.points_c, self.data_dimension))
            arr.attrs['data_type'] = "Image_ABC_1.0"
            arr.attrs['o'] = self.o
            arr.attrs['a'] = self.a
            arr.attrs['b'] = self.b
            arr.attrs['c'] = self.c
            arr.attrs['points_a'] = self.points_a
            arr.attrs['points_b'] = self.points_b
            arr.attrs['points_c'] = self.points_c
            arr.attrs['data_dimensions'] = self.data_dimension
            return arr._v_pathname

    def data(self):
        self.flush()
        with self._tc as th:
            node = th.tables.get_node(self._data)
            return np.array(node)

    def record(self, indices, count_data):
        # Add new data to a thread-safe queue for later insertion from the storage thread
        self._queue.put((indices, count_data))

    def flush(self):
        if self._queue.empty():
            return
        with self._tc as th:
            while not self._queue.empty():
                indices, count_data = self._queue.get()
                node = th.tables.get_node(self._data)
                # insert the data into the array as if it was flattened
                # documentation says None is valid and means an implicit reshape
                #np.put_along_axis(node, indices, count_data, axis=None)
                write_to_h5array_4d(node, indices, count_data)


class XYZScan(ParallelepipedScan):

    def __init__(self, x0: float, x1: float, x_px: int, y0: float, y1: float, y_px: int, z0, z1, z_px: int, data_dim=1):
        o = np.array([x0, y0, z0])
        a = np.array([x1, y0, z0])
        b = np.array([x0, y1, z0])
        c = np.array([z0, y0, z1])
        super(XYZScan, self).__init__(o, a, b, c, x_px, y_px, z_px, data_dim)


class ParallelogramScan(scan.ParallelogramScan):

    def __init__(self,
                 tc: TablesContext,
                 o: np.array,
                 a: np.array,
                 b: np.array,
                 a_px: int,
                 b_px: int,
                 data_dim=1):
        self._tc = tc
        self._queue = Queue()
        super(ParallelogramScan, self).__init__(o, a, b, a_px, b_px, data_dim)

    def initialise_data(self):
        with self._tc as th:
            ts = self._tc.timestamp()
            name = 'AB_{}'.format(ts)
            arr = th.tables.create_array("/Confocal/AB",
                                         name,
                                         createparents=True,
                                         atom=Float64Atom(),
                                         shape=(self.points_a, self.points_b, 1, self.data_dimension))
            arr.attrs['data_type'] = "Image_AB_1.0"
            arr.attrs['o'] = self.o
            arr.attrs['a'] = self.a
            arr.attrs['b'] = self.b
            arr.attrs['points_a'] = self.points_a
            arr.attrs['points_b'] = self.points_b
            arr.attrs['data_dimensions'] = self.data_dimension

            return arr._v_pathname

    def data(self):
        self.flush()
        with self._tc as th:
            node = th.tables.get_node(self._data)
            return np.array(node)

    def record(self, indices, count_data):
        # Add new data to a thread-safe queue for later insertion from the storage thread
        self._queue.put((indices, count_data))

    def flush(self):
        if self._queue.empty():
            return
        with self._tc as th:
            while not self._queue.empty():
                indices, count_data = self._queue.get()
                node = th.tables.get_node(self._data)
                # insert the data into the array as if it was flattened
                write_to_h5array_3d(node, indices, count_data)

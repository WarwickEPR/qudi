from abc import ABC, abstractmethod
import numpy as np


class ArbitraryScan(ABC):

    @abstractmethod
    def points(self):
        return iter(())

    @abstractmethod
    def extremal_points(self):
        return list()

    @abstractmethod
    def record(self, indices, count_data):
        return

    @abstractmethod
    def data(self):
        return np.array([])

    @abstractmethod
    def length(self):
        return 0

    @abstractmethod
    def done(self):
        return 0


class ParallelepipedScan(ArbitraryScan):

    def __init__(self, o: np.array, a: np.array, b: np.array, c: np.array, a_px: int, b_px: int, c_px: int, data_dim=1):
        self.o = o
        self.a = a
        self.b = b
        self.c = c
        self.A = self.a - self.o
        self.B = self.b - self.o
        self.C = self.c - self.o
        self.a_px = a_px
        self.b_px = b_px
        self.c_px = c_px
        self.data_dim = data_dim

        self._data = self.initialise_data()
        self._done = 0

    def initialise_data(self):
        return np.zeros((self.a_px*self.b_px*self.c_px, self.data_dim))

    @property
    def points_a(self):
        return self.a_px

    @property
    def points_b(self):
        return self.b_px

    @property
    def points_c(self):
        return self.c_px

    @property
    def data_dimension(self):
        return self.data_dim

    def points(self):
        for u in np.linspace(0, 1, self.a_px):
            for v in np.linspace(0, 1, self.b_px):
                for w in np.linspace(0, 1, self.c_px):
                    yield self.o + self.A * u + self.B * v + self.C * w

    def done(self):
        return self._done

    def extremal_points(self):
        return [self.o, self.a, self.b, self.c]

    def data(self):
        return np.reshape(self._data, (self.a_px, self.b_px, self.c_px, self._data.shape[1]))

    def record(self, indices, count_data):
        np.put_along_axis(self._data, indices, count_data, 0)
        self._done = max(indices)

    def length(self):
        return self.a_px * self.b_px * self.c_px


class XYZScan(ParallelepipedScan):

    def __init__(self, x0: float, x1: float, x_px: int, y0: float, y1: float, y_px: int, z0, z1, z_px: int, data_dim=1):
        o = np.array([x0, y0, z0])
        a = np.array([x1, y0, z0])
        b = np.array([x0, y1, z0])
        c = np.array([z0, y0, z1])
        super().__init__(o, a, b, c, x_px, y_px, z_px, data_dim)


class ParallelogramScan(ArbitraryScan):

    def __init__(self, o: np.array, a: np.array, b: np.array, a_px: int, b_px: int, data_dim=1):
        self.o = o
        self.a = a
        self.b = b
        self.A = self.a - self.o
        self.B = self.b - self.o
        print("b, o in PS: {} {}".format(self.o, self.b))
        print("A in PS: {}".format(self.A))
        print("B in PS: {}".format(self.B))
        self.a_px = a_px
        self.b_px = b_px
        self.data_dim = data_dim
        self._data = self.initialise_data()
        self._done = 0

    def initialise_data(self):
        return np.zeros((self.a_px*self.b_px, self.data_dim))

    def points(self):
        for u in np.linspace(0, 1, self.a_px):
            for v in np.linspace(0, 1, self.b_px):
                yield self.o + self.A * u + self.B * v

    def done(self):
        return self._done

    @property
    def points_a(self):
        return self.a_px

    @property
    def points_b(self):
        return self.b_px

    @property
    def data_dimension(self):
        return self.data_dim

    def extremal_points(self):
        return [self.o, self.a, self.b]

    def data(self):
        return np.reshape(self._data, (self.a_px, self.b_px, self._data.shape[1]))

    def record(self, indices, count_data):
        np.put_along_axis(self._data, indices, count_data, 0)
        self._done = max(indices)

    def length(self):
        return self.a_px * self.b_px


import numpy as np
from enum import Enum
from copy import copy

from numpy.linalg import norm

from . tables_context import TablesContext
from . tilt import Tilt

class Orientation(Enum):
    XY = 0
    XZ = 1
    YZ = 2


# Image arrays
# N-dimensional image with M columns of data
# For an "XY" image with/without tilt correction "img", img[i][j][0] = [x, y, z, countrate]
# For an "XZ" image with/without tilt correction "img", img[i][0][j] = [x, y, z, countrate]
# For a "YZ" image with/without tilt correction "img", img[0][i][j] = [x, y, z, countrate]
# Additional data columns can be appended e.g. for a second counter channel or for a n-point sweep of another param
# For a volume image, img[i][j][k] = [x, y, z, countrate]
# The order of physical axis sweep is recorded in the attribute "axis_order"
# This retains the logical structure of the scan in the multi-dimensional array structure as well as the actual coords
# In addition to recording the point coords, the sweep used for each axis (default: linear) is recorded in the attributes
# The classes below provide a representation of this data and conversion from other formats

# Attributes:
# axis_sweep_order
# axis_extent[n] = {label='X', start=1e-6, end=2e-6, points=100}
# image_type = 'XY', 'Volume', ... (hint for interpretation)
# tilt_correction = [phi, psi, theta]
# tilt_correction_origin = [x, y, z]
# data_columns = ['countrate']
# manual_stage_X = 5.10
# manual_stage_Y = 4.81
# laser_power = 0.001
# notes = "Additional notes entered by the user"

class NodeHDF:

    def __init__(self, tc: TablesContext, path: str):
        self.tc = tc
        self.path = path
        self._node = None

    @staticmethod
    def access(method):
        def wrapped(ref, *args, **kwargs):
            with ref.tc as th:
                ref._node = th.tables.get_node(ref.path)
                return method(ref, *args, **kwargs)
        return wrapped


class FileHDF:

    def __init__(self, hdf_file: str):
        self._tc = TablesContext(hdf_file)


class ImageHDF(NodeHDF):

    def __init__(self, tc: TablesContext, path: str):
        super(ImageHDF, self).__init__(tc, path)
        self.tc = tc
        self.path = path
        self._node = None

    # access the whole 4d array
    @property
    @NodeHDF.access
    def data(self):
        return np.array(self._node)

    @property
    @NodeHDF.access
    def attrs(self):
        return dict([(k, self._node.attrs[k]) for k in self._node.attrs._f_list()])

    @property
    @NodeHDF.access
    def title(self):
        return self._node._v_title

    @title.setter
    @NodeHDF.access
    def title(self, title):
        self._node._v_title = title

    # get a 2d image as a 2d array

    @property
    @NodeHDF.access
    def image_type(self):
        try:
            data_type = self._node.attrs.data_type
        except AttributeError:
            return ''

        try:
            s = data_type.split('_')
            if len(s) == 3:
                prefix, img_type, version = s
            elif len(s) == 2:
                img_type, version = s
                prefix = ''
            return img_type
        except ValueError:
            return data_type

    @NodeHDF.access
    def xy_image_data(self, z_slice=0, data_column=0):
        s = self._node.shape
        image = None
        if s[-1] < 4:
            # oops, no coords
            dc = data_column
        else:
            dc = 3 + data_column
        if len(s) == 3:
            # oops, early version, one slice
            image = np.array(self._node[:, :, dc])
        else:
            image = np.array(self._node[:, :, z_slice, dc])
#        image = np.array(self._node[:, :, z_slice, 3 + data_column])
        # axis_sweep_order
        # axis_extent[n] = {label='X', start=1e-6, end=2e-6, points=100}
        # image_type = 'XY', 'Volume', ... (hint for interpretation)
        # tilt_correction = [phi, psi, theta]
        # tilt_correction_origin = [x, y, z]
        # data_columns = ['countrate']
        # manual_stage_X = 5.10
        # manual_stage_Y = 4.81
        # laser_power = 0.001
        # notes = "Additional notes entered by the user"

        # extract all the user attributes, image metadata
        data = dict([(x, self._node.attrs[x]) for x in self._node.attrs._v_attrnamesuser])
        data['image'] = image
        return data

    @NodeHDF.access
    def xz_image_data(self, y_slice=0, data_column=0):
        image = np.array(self._node[:, y_slice, :, 3 + data_column])
        data = dict([(x, self._node.attrs[x]) for x in self._node.attrs._v_attrnamesuser])
        data['image'] = image
        return data


    @NodeHDF.access
    def yz_image_data(self, x_slice=0, data_column=0):
        image = np.array(self._node[:, x_slice, :, 3 + data_column])
        data = dict([(x, self._node.attrs[x]) for x in self._node.attrs._v_attrnamesuser])
        data['image'] = image
        return data


    # get a 3d image as a 3d array

    @NodeHDF.access
    def volume_data(self, data_column=0):
        image = np.array(self._node[:, :, :, 3 + data_column])
        data = dict([(x, self._node.attrs[x]) for x in self._node.attrs._v_attrnamesuser])
        data['image'] = image
        return data


class Rectangle:

    # stored as an origin point and two side vectors

    def __init__(self, skew_rectangle=None, tilt: Tilt = None):
        if skew_rectangle is not None and tilt is not None:
            g = skew_rectangle  # 10x2 geometry in m
            ox = g[0][3]
            oy = g[1][3]
            ax = g[0][2]
            ay = g[1][2]
            bx = g[0][0]
            by = g[1][0]

            self.o = tilt.point_from_xy(ox, oy)
            self.a = tilt.point_from_xy(ax, ay)
            self.b = tilt.point_from_xy(bx, by)
            self.A = self.a-self.o
            self.B = self.b-self.o

    @property
    def centre(self):
        return self.o + self.A * .5 + self.B * .5

    @property
    def norm(self):
        n = np.cross(self.A, self.B)
        if n[2] < 0:
            # reverse if "down"
            n = -n
        return n / norm(n)

    @property
    def side_lengths(self):
        return norm(self.A), norm(self.B)

    def extents(self):
        return self.side_lengths

    def fixed_aspect_resolution(self, resolution):
        xd, yd = self.side_lengths
        if xd < yd:
            sy = resolution
            sx = int(sy * xd / yd)
        else:
            sx = resolution
            sy = int(sx * yd / xd)
        return sx, sy

    def displaced(self, z):
        r = copy(self)
        r.o = self.o + self.norm * z
        return r

    def __str__(self):
        return "Rectangle o={}, a={}, b={}, extent={}".format(self.o, self.a, self.b, self.extents())

    def __repr__(self):
        return str(self)


class Cuboid(Rectangle):

    def __init__(self, height=0, **kwargs):
        super(Cuboid).__init__(**kwargs)
        self.height = height
        self.C = self.norm * height
        self.c = self.o + self.C

    def extents(self):
        x, y = self.side_lengths
        return x, y, self.height

    def __str__(self):
        return "Cuboid o={}, a={}, b={}, c={}, extent={}".format(self.o, self.a, self.b, self.c, self.extents())

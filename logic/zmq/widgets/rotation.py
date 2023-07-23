from traitlets import HasTraits, Float, Tuple, default
import numpy as np
from numpy.linalg import norm
import tabulate


class Rotation(HasTraits):
    xy_norm = Tuple(Float(), Float(), Float())
    pivot_point = Tuple(Float(), Float(), Float())   # x, y, z in stage coordinates
    rotation = Float()  # radians, about z axis

    # Uses information attached to images as attributes when acquired
    # Tilt is the Qudi "dz" correction for imaging
    #   In displaying images, if this is present just display the tilt correction used
    # This is convenient as Qudi supports it and you get an integrated image in the UI
    # Rotation is the rotation about the norm of this tilted XY plane through a point to aid lining up "nice" arrays
    # This can be used in "arbitrary scans" to efficiently acquire images of arrays at an angle to the stage
    # and should display with X' and Y' axes to avoid confusion
    # Any POIs are recorded in their current orientation in stage position.
    # If the displayed image is rotated, they will need to be rotated about the pivot also for display and labelling.
    # When visiting POIs, imaging rotations and tilt corrections don't matter.
    # You're going to a stage position in the current ROI and displaying it in a rotated/tilted context

    # When the stage position or sample orientation changes you should start a new empty ROI
    # POIs can be imported from an old ROI as long as you can identify one / two points in both. On import the POIs
    # can be rotated and translated.
    # ROIs can be populated by pulling from Qudi or from point identification in imaging from 2D or 3D information
    # ROIs record relative positions of sites with reference to relevant imaging for context
    # When an ROI is active, note the current ROI with the images acquired and allow these to be selected in the ROI display

    # To scan a rotated rectangle:
    #  Enter three points in stage coordinates and the resolution in each direction
    # or:
    #  Enter points to establish tilt correction
    #  Enter two points which identify 'x' edge and am orthogonal distance for y with sign
    # This implies you've already imaged with tilt correction but without the rotation

    # To scan a thin slab:
    #  Select a rectangle and a depth with resolution

    def __init__(self, xy_norm=(0, 0, 1), pivot=(0, 0, 0), rotation=0, **kwargs):
        super(Rotation, self).__init__(**kwargs)
        self.xy_norm = xy_norm
        self.pivot_point = pivot
        self.rotation = rotation

    @default('pivot_point')
    def _default_pivot_point(self):
        return 0, 0, 0

    @default('xy_norm')
    def _default_xy_norm(self):
        return 0, 0, 1

    @default('rotation')
    def _default_rotation(self):
        return 0

    # The normal to a tilted X-Y plane is unambiguous and works okay with the Euler rotation approximation in Qudi
    def set_tilt_from_points(self, p0: np.array, p1: np.array, p2: np.array):
        zp = np.cross(p1-p0, p2-p0)
        self.xy_norm = zp / norm(zp)  # normalized z' unit vector

    # Tilts are expected to be small (Qudi expects) so handle more or less as in Qudi
    # Works for small angles

    def tilt_x(self):
        p = np.array(*self.pivot_point)
        z = np.array(*self.xy_norm)
        # x plane projection
        zx = z
        zx[1] = 0
        zx = zx / norm(zx)
        return np.dot(z, zx)

    def tilt_y(self):
        p = np.array(*self.pivot_point)
        z = np.array(*self.xy_norm)
        # x plane projection
        zy = z
        zy[1] = 0
        zy = zy / norm(zy)
        return np.dot(z, zy)

    def _push_to_qudi(self):
        # Need to set tilt_x, tilt_y already in the correct form for tilt_variable_ax, tilt_variable_ay
        # along with tilt_reference_x and tilt_reference_y
        # z Doesn't actually appear in Qudi version but keep it for arbitrary scan rotation and compatibility with ROIs
        pass

    def display_only(self):
        x, y, z = self.pivot_point
        data = [['Tilt X:', '{} mrad'.format(np.acos(self.tilt_x()) * 1e3)],
                ['Tilt Y:', '{} mrad'.format(np.cos(self.tilt_y()) * 1e3)],
                ['Pivot about:', '({}, {}, {}) \u039cm'.format(x*1e6, y*1e6, z*1e6)],
                ['Rotation about pivot:', '{} \u00b0'.format(self.rotation * 180 / np.pi)]]
        return tabulate.tabulate(data, tablefmt='html')
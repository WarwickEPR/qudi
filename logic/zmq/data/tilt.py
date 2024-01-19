import numpy as np
from numpy.linalg import norm


class Tilt:

    # An invariate pivot point and three points in a plane is enough to define a tilt
    # or equally an invariate point and norm or Euler angles
    def __init__(self, pivot=np.array([0, 0, 0]), p0=None, p1=None, p2=None):
        self.pivot = pivot
        self.xy_norm = np.array([0, 0, 1])
        self.theta_x = 0.0
        self.theta_y = 0.0

        if p0 is not None and p1 is not None and p2 is not None:
            # Really just to store and recover
            self.p0 = p0
            self.p1 = p1
            self.p2 = p2

            zp = np.cross(p1 - p0, p2 - p0)
            n = norm(zp)
            if n == 0:
                self.xy_norm = np.array([0, 0, 1])
            else:
                if zp[2] < 0:
                    # tilted plane has upwards normal regardless of point order
                    zp = -zp
                self.xy_norm = zp / n  # normalized z' unit vector

            self.theta_x = np.arccos(np.dot(self.xy_norm, np.array([1, 0, 0]))) - np.pi / 2
            self.theta_y = np.arccos(np.dot(self.xy_norm, np.array([0, 1, 0]))) - np.pi / 2

    def point_from_xy(self, x, y):
        z = self.pivot[2] + (x - self.pivot[0]) * self.xy_norm[0] + (y - self.pivot[1]) * self.xy_norm[1]
        return np.array([x, y, z])


# Tilt without the small angle approximation
class TiltOld:
    def __init__(self, pivot_point=np.array([0, 0, 0]), tilt_norm=np.array([0, 0, 1])):
        self._pivot = pivot_point
        # ensure _norm is a unit vector
        self._norm = tilt_norm / norm(tilt_norm)

        # rotation axis and angle between stage z and tilted z
        z0 = np.array([0, 0, 1])
        axis = np.cross(z0, self._norm)
        if axis[0] < 0 or axis[1] < 0:
            axis = -axis
        p, q, r = self._rotation_axis = axis
        c = np.dot(z0, self._norm)
        s = np.sqrt(1-c*c)
        self._rotation_angle = np.arccos(c)

        # transform into a matrix rotation
        skew = np.array([[0, -r, q], [q, 0, -p], [-q, p, 0]])
        self._rotation = c * np.identity(3) + c * skew + (1-c) * np.outer(axis, axis)

    def tilted_xy(self, x, y):
        p = np.array([x, y, self._pivot[2]])
        return self.tilted(p)

    def tilted(self, p: np.array):
        q = p - self._pivot
        # translate to put pivot at origin, rotate, translate back
        return np.matmul(self._rotation, q) + self._pivot


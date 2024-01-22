import numpy as np
from numpy.linalg import norm


# Tilt without the small angle approximation
# Pivots about an invariant point to a plane defined by three points
class Tilt:
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

        # rotation axis and angle between stage z and tilted z
        z0 = np.array([0, 0, 1])
        axis = np.cross(z0, self.xy_norm)
        if axis[0] < 0 or axis[1] < 0:
            axis = -axis
        p, q, r = self._rotation_axis = axis
        c = np.dot(z0, self.xy_norm)
        s = np.sqrt(1-c*c)
        self.angle_to_vertical = np.arccos(c)
        self.theta_x = np.arccos(np.dot(self.xy_norm, np.array([1, 0, 0]))) - np.pi / 2
        self.theta_y = np.arccos(np.dot(self.xy_norm, np.array([0, 1, 0]))) - np.pi / 2

        # transform into a matrix rotation
        skew = np.array([[0, -r, q], [q, 0, -p], [-q, p, 0]])
        self.rotation = c * np.identity(3) + c * skew + (1-c) * np.outer(axis, axis)

    def point_from_xy(self, x, y):
        p = np.array([x, y, self.pivot[2]])
        return self.tilted(p)

    def tilted(self, p: np.array):
        # translate to put pivot at origin, rotate, translate back
        return np.matmul(self.rotation, p-self.pivot) + self.pivot

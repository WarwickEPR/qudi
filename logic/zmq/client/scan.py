from .QudiControl import QudiClient
import numpy as np
from numpy.linalg import norm


# Tilt without the small angle approximation
class Tilt:
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


class ArbitraryScan(QudiClient):

    name = "scan"

    def __init__(self, *args, **kwargs):
        super(ArbitraryScan, self).__init__(*args, **kwargs)
        self._scan_attrs = {}

    async def start_cuboid_scan(self,
                                pivot=np.array([0, 0, 0]),      # describes point on plane
                                tilt_norm=np.array([0, 0, 1]),  # describes plane orientation
                                o0=0.0,   # together describe one edge line in tilted plane
                                o1=0.0,
                                a0=1.0,
                                a1=0.0,
                                b0=0.0,   # a point on the opposite edge of the rectangle describing its height, in the plane
                                b1=1.0,
                                up=1.0,    # distance above the tilt corrected plane
                                down=1.0,  # distance below the tilt corrected plane
                                size=(1, 1, 1)):    # pixels in direction OA, OB and OC
        px, py, pz = size
        tilt = Tilt(pivot, tilt_norm)
        om = tilt.tilted_xy(o0, o1)

        # three of the cuboid corners using an edge and the norm of the plane
        o = om - tilt_norm * down
        c = om + tilt_norm * up
        a = tilt.tilted_xy(a0, a1) - tilt_norm * down

        # As we want a cuboid rather than general parallelepiped we need the height to point b
        # First find point b on the tilted plane
        b = tilt.tilted_xy(b0, b1) - tilt_norm * down

        # Calculate the last corner so the edge is perpendicular to the other two
        # and b lies on the far edge
        bp = self._rect_corner(o, a, tilt_norm, b)

        # context information to add to stored attributes
        self._scan_attrs = {'pivot': pivot,
                            'tilt_norm': tilt_norm}

        message_body = {'origin': o, 'a': a, 'b': bp, 'c': c, 'points_a': px, 'points_b': py, 'points_c': pz}
        await self.send_command('start_parallelepiped_scan', message_body)

    async def start_rectangle_scan(self,
                                   pivot=np.array([0, 0, 0]),      # describes point on plane
                                   tilt_norm=np.array([0, 0, 1]),  # describes plane orientation
                                   o0=0.0,   # together describe one edge line in tilted plane
                                   o1=0.0,
                                   a0=1.0,
                                   a1=0.0,
                                   b0=0.0,   # a point on the opposite edge of the rectangle describing its height, in the plane
                                   b1=1.0,
                                   size=(1, 1)):    # pixels in direction OA and OB
        px, py = size
        tilt = Tilt(pivot, tilt_norm)
        o = tilt.tilted_xy(o0, o1)
        a = tilt.tilted_xy(a0, a1)
        b = tilt.tilted_xy(b0, b1)

        # context information to add to stored attributes
        self._scan_attrs = {'pivot': pivot,
                            'tilt_norm': tilt_norm}

        # Calculate the last corner so the edge is perpendicular to the other two
        # and b lies on the far edge
        bp = self._rect_corner(o, a, tilt_norm, b)
        message_body = {'origin': o, 'a': a, 'b': bp, 'points_a': px, 'points_b': py}
        await self.send_command('start_parallelogram_scan', message_body)

    async def scan_updates(self):
        return self.subscribe('scan.update')

    async def scan_finished(self):
        s = self.subscribe('scan.finished')
        await s.receive()

    @staticmethod
    def _height(v, p):
        return norm(np.cross(v, p)) / norm(v)

    @classmethod
    def _rect_corner(cls, o, a, n, b):

        # height of b from edge oa
        h = cls._height(a-o, b-o)

        # the final corner is perpendicular to the other two from o with length h
        oa = a-o
        d = np.cross(n, oa/norm(oa))
        return o + d * h


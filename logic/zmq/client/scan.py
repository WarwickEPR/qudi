from .QudiControl import QudiClient
import numpy as np
from numpy.linalg import norm
from ..data.image import Cuboid


class ArbitraryScan(QudiClient):

    name = "scan"

    def __init__(self, *args, **kwargs):
        super(ArbitraryScan, self).__init__(*args, **kwargs)
        self._scan_attrs = {}

    async def start_cuboid_scan(self, cuboid: Cuboid, size=(1, 1, 1)):
        pa, pb, pc = size

        message_body = {'origin': cuboid.o,
                        'a': cuboid.a, 'b': cuboid.b, 'c': cuboid.c,
                        'points_a': pa, 'points_b': pb, 'points_c': pc}
        await self.send_command('start_parallelepiped_scan', message_body)

    async def start_rectangle_scan(self, rectangle, size=(1, 1)):
        pa, pb = size
        message_body = {'origin': rectangle.o, 'a': rectangle.a, 'b': rectangle.b, 'points_a': pa, 'points_b': pb}
        await self.send_command('start_parallelogram_scan', message_body)

    async def scan_updates(self):
        return self.subscribe('scan.update')

    async def scan_finished(self):
        s = self.subscribe('scan.finished')
        await s.receive()

    async def stop(self):
        await self.send_command('stop')

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


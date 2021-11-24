from .QudiControl import QudiClient
from .. common import Orientation


class Confocal(QudiClient):

    name = "confocal"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def start_xy_scan(self, x0=None, x1=None, y0=None, y1=None, z=None, resolution=None):
        p = {'x0': x0, 'x1': x1, 'y0': y0, 'y1': y1, 'z': z,
             'resolution': resolution, 'orientation': Orientation.XY.name}
        await self.send_command('start_scan', body=p)

    async def start_xz_scan(self, x0=None, x1=None, z0=None, z1=None, y=None, resolution=None):
        p = {'x0': x0, 'x1': x1, 'z0': z0, 'z1': z1, 'y': y,
             'resolution': resolution, 'orientation': Orientation.XZ.name}
        await self.send_command('start_scan', body=p)

    async def start_yz_scan(self, y0=None, y1=None, z0=None, z1=None, x=None, resolution=None):
        p = {'y0': y0, 'y1': y1, 'z0': z0, 'z1': z1, 'x': x,
             'resolution': resolution, 'orientation': Orientation.YZ.name}
        await self.send_command('start_scan', body=p)

    async def stop_scan(self):
        await self.send_command('stop')

    async def save_xy(self):
        await self.send_command('save_xy')

    async def save_depth(self):
        await self.send_command('save_depth')

    async def scan_stopped(self):
        s = self.client.subscribe('confocal.stopped')
        await s.receive()

    async def scan_updates(self):
        s = self.client.subscribe('confocal.update')
        await s.receive()

    async def xy_image_started(self):
        s = self.client.subscribe('confocal.xy_image_started')
        msg = await s.receive()
        self.log("XY image started: {}", msg)
        return msg

    async def depth_image_started(self):
        s = self.client.subscribe('confocal.depth_image_started')
        msg = await s.receive()
        self.log("Depth image started: {}", msg)
        return msg

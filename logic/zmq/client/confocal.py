import asyncio

from .QudiControl import QudiClient
from .. data.image import Orientation


class Confocal(QudiClient):

    name = "confocal"

    def __init__(self, *args, **kwargs):
        super(Confocal, self).__init__(*args, **kwargs)
        self._monitor_position = False
        self._x = self._y = self._z = 0

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
        s = self.subscribe('confocal.stopped')
        await s.receive()

    async def scan_updates(self):
        s = self.subscribe('confocal.update')
        await s.receive()

    def monitor_position_changes(self):
        s = self.subscribe('confocal.position_changed_to')
        if not self._monitor_position:
            self._monitor_position = True

            async def monitor():
                while self._monitor_position:
                    m = await s.receive()
                    self._x = m.body['x']
                    self._y = m.body['y']
                    self._z = m.body['z']
                    self.log.debug("Position updated to: {}, {}, {}".format(self._x, self._y, self._z))

            asyncio.create_task(monitor())

    # If monitoring position change reports from Qudi, return the latest reported position synchronously
    def get_latest_position(self):
        return self._x, self._y, self._z

    async def xy_image_started(self):
        s = self.subscribe('confocal.xy_image_started')
        msg = await s.receive()
        self.log("XY image started: {}", msg)
        return msg

    async def depth_image_started(self):
        s = self.subscribe('confocal.depth_image_started')
        msg = await s.receive()
        self.log("Depth image started: {}", msg)
        return msg

    async def get_position(self):
        await self.send_command('get_position')
        msg = await self.receive_message()
        return msg.body

    async def set_position(self, x=None, y=None, z=None, a=None):
        p = {}
        if x is not None: p['x'] = x
        if y is not None: p['y'] = y
        if z is not None: p['z'] = z
        if a is not None: p['a'] = a
        await self.send_command('set_position', body=p)

    async def set_tilt(self, tilt_x=0, tilt_y=0, reference_x=0, reference_y=0):
        tilt = {'tilt_x': tilt_x,
                'tilt_y': tilt_y,
                'reference_x': reference_x,
                'reference_y': reference_y}
        await self.send_command('set_tilt', body=tilt)

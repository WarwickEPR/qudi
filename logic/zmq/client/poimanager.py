from .QudiControl import QudiClient


class PoiManagerClient(QudiClient):

    name = "poimanager"

    def __init__(self, *args, **kwargs):
        super(PoiManagerClient, self).__init__(*args, **kwargs)

    async def reset_roi(self, name=None):
        return await self.query('reset_roi', {'name': name})

    async def save_roi(self, name=None):
        return await self.query('save_hdf5', {'name': name})

    async def goto_poi(self, name):
        await self.send_command('goto_poi', name)

    async def optimize_poi(self, name, update=True):
        await self.send_command('optimize_poi', body={'name': name, 'update': update})

    async def add_pois(self, pois: list):
        return await self.query('add_pois', pois)

    async def list_pois(self):
        return await self.query('list_pois')

    async def poi_dict(self):
        return await self.query('poi_dict')

    async def set_active_poi(self, poi):
        await self.send_command('set_active_poi', poi)

    async def start_tracking(self, poi=None):
        return await self.query('start_tracking', poi)

    async def stop_tracking(self):
        return await self.query('stop_tracking')

    async def pending_optimize(self):
        optimized = self.subscribe('reoptimized')

        async def awaitable():
            return await optimized.receive()

        return awaitable()

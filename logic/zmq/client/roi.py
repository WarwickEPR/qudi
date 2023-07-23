from .QudiControl import QudiClient


class RoiClient(QudiClient):

    name = "roi"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def reset_roi(self, name=None):
        await self.send_command('reset_roi', {'name': name})
        await self.receive_message()

    async def save_roi(self, name=None):
        await self.send_command('save_roi', {'name': name})

    async def goto_poi(self, name):
        await self.send_command('goto_poi', name)

    async def optimize_poi(self, name, update=True):
        await self.send_command('optimize_poi', body={'name': name, 'update': update})

    async def add_pois(self, pois: list):
        await self.send_command('add_pois', pois)
        await self.receive_message()

    async def list_pois(self):
        return await self.query('list_pois')

    async def poi_dict(self):
        return await self.query('poi_dict')

    async def set_active_poi(self, poi):
        await self.send_command('set_active_poi', poi)

    async def start_tracking(self, poi=None):
        await self.send_command('start_tracking', poi)
        await self.receive_message()

    async def stop_tracking(self):
        await self.send_command('stop_tracking')
        await self.receive_message()

    async def wait_for_optimizer(self):
        n = self.subscribe('reoptimized')
        response = await n.receive()
        return



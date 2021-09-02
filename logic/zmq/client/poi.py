from .QudiControl import QudiClient, BgTask


class PoiClient(QudiClient):

    name = "poi"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def reset_roi(self, name=None):
        await self.send_command('reset_roi', {'name': name})

    async def save_roi(self, name=None):
        await self.send_command('save_roi', {'name': name})

    async def add_pois(self, pois: list):
        await self.send_command('save_roi', pois)
        await self.receive_message()

    async def start_tracking(self, poi=None):
        await self.send_command('start_tracking', poi)

    async def stop_tracking(self):
        await self.send_command('stop_tracking')




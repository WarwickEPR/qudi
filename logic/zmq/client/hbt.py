from .QudiControl import QudiClient


class Hbt(QudiClient):

    name = "hbt"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def start(self):
        await self.send_command('start')

    async def stop(self):
        await self.send_command('stop')

    async def emit(self):
        await self.send_command('emit')

    async def save(self):
        await self.send_command('save')

    async def save_hdf(self):
        await self.send_command('save_hdf')

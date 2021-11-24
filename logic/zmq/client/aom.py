from .QudiControl import QudiClient, BgTask


class Aom(QudiClient):

    name = "aom"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def take_psat(self):
        await self.send_command('take_psat')

    async def emit_psat(self):
        await self.send_command('emit')

    async def save(self):
        await self.send_command('save')

    async def save_hdf(self):
        await self.send_command('save_hdf')

    async def set_power(self, power):
        await self.send_command('set_power', body=power)

    async def get_power(self):
        await self.send_command('get_power')
        power = await self.receive_message()
        return power

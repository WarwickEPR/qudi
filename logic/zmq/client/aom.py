from .QudiControl import QudiClient
import logging


class Aom(QudiClient):

    name = "aom"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def set_power(self, power):
        await self.send_command('set_power', body=power)

    async def get_power(self):
        await self.send_command('get_power')
        msg = await self.receive_message()
        power = msg.body
        return power

    def take_psat(self):
        self.send_command('take_psat')

    async def save_psat_hdf5(self, tag=''):
        await self.send_command('save_psat_hdf5', {'tag': tag})

    async def save_psat_qudi(self, tag=''):
        await self.send_command('save_psat_qudi', {'tag': tag})

    async def emit_psat(self):
        await self.send_command('emit_psat')

    def pending_psat_fit(self):
        s = self.subscribe('psat.fitted')

        async def awaitable():
            response = await s.receive()
            return response.body

        return awaitable()

    def pending_psat_data(self):
        s = self.subscribe('psat.data')

        async def awaitable():
            response = await s.receive()
            return response.body

        return awaitable()

    def pending_psat_saved(self):
        s = self.subscribe('psat.saved')

        async def awaitable():
            response = await s.receive()
            return response.body.get('path', None)

        return awaitable()

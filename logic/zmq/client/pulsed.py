from .QudiControl import QudiClient
from .. common import Orientation

class Pulsed(QudiClient):

    name = "pulsed"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def generate_predefined(self, sequence, params):
        s = self.subscribe('pulsed.sequence_generated')
        await self.send_command('generate_predefined', body={'name': sequence, 'parameters': params})
        await s.receive()

    async def start(self):
        await self.send_command('start')

    async def stop(self):
        await self.send_command('stop')

    async def pause(self):
        await self.send_command('pause')

    async def unpause(self):
        await self.send_command('continue')


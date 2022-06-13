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
    
    async def wait_for_measurement_to_finish(self):
        s = self.subscribe('pulsed.measurement_finished')
        await s.receive()

    async def start(self, name=None, duration=None):
        body = {}
        if name is not None:
            body = {'name': name}
        if duration is not None:
            body.update({'duration': duration})

        if body != {}:
            await self.send_command('start', body=body)
        else: 
            await self.send_command('start')

    async def stop(self):
        await self.send_command('stop')

    async def pause(self):
        await self.send_command('pause')

    async def unpause(self):
        await self.send_command('continue')

    async def save_qudi(self):
        await self.send_command('save_qudi')


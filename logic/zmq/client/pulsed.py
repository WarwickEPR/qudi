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

    async def perform_fit(self, fit_name):
        s = self.subscribe('pulsed.fit_updated')
        await self.send_command('perform_fit', body={'fit_name': fit_name})
        response = await s.receive()
        return response.body

    async def set_microwave_settings(self, power=None, frequency_in_GHz=None, use_external_generator=True):
        body = {}
        if power is not None:
            body.update({'power': power})
        if frequency_in_GHz is not None:
            body.update({'frequency': frequency_in_GHz*1e9})
        body.update({'use_ext_microwave': use_external_generator})

        await self.send_command('set_microwave_settings', body=body)

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

    async def save_qudi(self, tag=''):
        if tag != '':
            await self.send_command('save_qudi', tag)
        else:
            await self.send_command('save_qudi')


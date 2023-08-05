from .QudiControl import QudiClient


class HbtClient(QudiClient):

    name = "hbt"

    def __init__(self, *args, **kwargs):
        super(HbtClient, self).__init__(*args, **kwargs)
        self.measurement = None

    async def start(self):
        await self.send_command('start')

    async def start_timed(self, time=60):
        await self.send_command('start_timed', {'time': time})

    async def stop(self):
        await self.send_command('stop')

    async def emit(self):
        await self.send_command('emit')

    def pending_done(self):
        s = self.subscribe('hbt.stopped')

        async def awaitable():
            # wait for the measurement to be stopped (by timer or otherwise)
            # blocks on notification, but this can be wrapped to time out or stop on a condition
            await s.receive()

        return awaitable()

    async def save_hdf5(self, tag=''):
        response = await self.send_command('save_hdf5', {'tag': tag})
        return response.body

    async def save_qudi(self, tag=''):
        response = await self.send_command('save_qudi', {'tag': tag})
        return response.body
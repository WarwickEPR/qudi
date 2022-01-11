from .QudiControl import QudiClient


class Odmr(QudiClient):

    name = "odmr"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def setup_scan(self, sweep=None, clock=None, oversampling=None, runtime=None):
        params = {}
        if sweep is not None: params['sweep'] = sweep
        if clock is not None: params['clock'] = clock
        if oversampling is not None: params['oversampling'] = oversampling
        if runtime is not None: params['runtime'] = runtime
        await self.send_command('setup_scan', body=params)

    async def stop_scan(self):
        await self.send_command('stop')

    async def save(self):
        await self.send_command('save')

    async def scan_stopped(self):
        s = self.subscribe('odmr.stopped')
        await s.receive()

    async def scan_updates(self):
        s = self.subscribe('odmr.update')
        await s.receive()
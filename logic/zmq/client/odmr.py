from .QudiControl import QudiClient


class Odmr(QudiClient):

    name = "odmr"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @staticmethod
    def _scan_params(sweep=None, clock=None, oversampling=None, runtime=None):
        params = {}
        if sweep is not None: params['sweep'] = sweep
        if clock is not None: params['clock'] = clock
        if oversampling is not None: params['oversampling'] = oversampling
        if runtime is not None: params['runtime'] = runtime
        return params

    async def setup_scan(self, **kwargs):
        p = self._scan_params(**kwargs)
        await self.send_command('setup_scan', body=p)

    async def start_scan(self, **kwargs):
        p = self._scan_params(**kwargs)
        status = await self.query('start_scan', body=p)
        if status != 'OK':
            self.log.warn('ODMR already running')
            return False
        else:
            return True

    async def stop_scan(self):
        await self.send_command('stop_scan')

    async def save(self):
        await self.send_command('save')

    async def save_qudi(self):
        await self.send_command('save_qudi')

    async def fit_qudi(self, fit_function=None, channel_index=0, fit_range=0):
        await self.send_command('fit', {'fit_function': fit_function,
                                        'channel_index': channel_index,
                                        'fit_range': fit_range})

    async def qudi_fit_functions(self):
        fit_functions = await self.query('fit_functions')
        return fit_functions

    # actually stopped
    async def scan_stopped(self):
        s = self.subscribe('odmr.stop')
        await s.receive()

    # actually started
    async def scan_started(self):
        s = self.subscribe('odmr.start')
        params = await s.receive()
        return params

    async def scan_fitted(self):
        s = self.subscribe('odmr.fit_updated')
        fit = await s.receive()
        return fit
from .QudiControl import QudiClient, BgTask
import logging


class Optimizer(QudiClient):

    name = "optimizer"

    def __init__(self, *args, **kwargs):
        super(Optimizer, self).__init__(*args, **kwargs)

    def start_refocus(self, poi=None):
        if poi is None:
            self.send_command('start_refocus')
        else:
            self.send_command('start_refocus', {'poi': poi})

    # See proxy.optimizer for setup params, e.g. xy_span
    def setup(self, setup: dict):
        self.send_command('setup', setup)

    async def save_hdf5(self):
        await self.send_command('save_hdf5')




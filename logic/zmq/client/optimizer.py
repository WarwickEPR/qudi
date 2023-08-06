from .QudiControl import QudiClient
import logging


class RefocusFailed(Exception):
    pass


class ZRefocusFailed(RefocusFailed):
    pass


class OptimizerClient(QudiClient):

    name = "optimizer"

    def __init__(self, *args, **kwargs):
        super(OptimizerClient, self).__init__(*args, **kwargs)
        self.log = logging.getLogger("OptimizerClient")

    async def refocus(self, poi=None, setup=None):
        if setup is not None:
            await self.setup(setup)
        self.log.info("Starting refocus")
        if poi is None:
            await self.send_command('refocus')
        else:
            await self.send_command('refocus', {'poi': poi})

    async def autosave_on_refocus(self, state=True):
        await self.send_command('autosave_on_refocus', state)

    async def stop_refocus(self):
        self.log.info("Stopping refocus")
        await self.send_command('stop_refocus')

    # See proxy.optimizer for setup params, e.g. xy_span
    async def setup(self, setup: dict):
        self.log.info("Changing optimizer window to {}".format(setup))
        await self.send_command('setup', setup)

    async def emit_refocused_position(self):
        await self.send_command('emit_refocused')

    async def save_hdf5(self):
        self.log.info("Saving to ")
        await self.send_command('save_hdf5')

    def pending_refocus(self):
        refocused = self.subscribe('optimizer.refocused')

        async def awaitable():
            result = await refocused.receive()
            self.log.info("Refocused: {}".format(result))
            return result.body

        return awaitable()

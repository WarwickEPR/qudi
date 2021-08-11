from .QudiControl import QudiClient


class Optimizer(QudiClient):

    name = "optimizer"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def start_refocus(self):
        await self.send_command('refocus', {'poi': ''})

    async def push_data(self):
        await self.send_command('push_data', '')

    async def wait_for_refocus(self):
        s = self.subscribe('refocused')
        response = await s.receive()
        print("Position: {}".format(response))

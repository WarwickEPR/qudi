from .QudiControl import QudiClient
import PIL.Image
import IPython.display


class Optimizer(QudiClient):

    name = "optimizer"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def start_refocus(self):
        await self.send_command('refocus', {'poi': ''})

    async def push_data(self):
        await self.send_command('push_data', '')

    async def wait_for_refocus(self):
        s = self.subscribe('optimizer.refocused')
        response = await s.receive()
        print("Position: {}".format(response))

    async def display(self):
        s = self.subscribe('optimizer.data')
        data = await s.receive()
        if 'xy_data' in data:
            IPython.display.display(PIL.Image.fromarray(data['xy_data']))

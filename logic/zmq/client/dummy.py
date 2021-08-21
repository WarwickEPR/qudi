from .QudiControl import QudiClient


class Dummy(QudiClient):

    name = "dummy"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def echo(self, x):
        await self.send_command('echo', body=x)
        reply = await self.receive_message()
        return reply.contents


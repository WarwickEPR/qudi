from .QudiControl import QudiClient, BgTask


class PsatClient(QudiClient):

    name = "psat"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def take_psat(self, name=None):
        await self.send_command('take_psat')




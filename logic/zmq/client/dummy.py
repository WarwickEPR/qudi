from .QudiControl import QudiClient


class Dummy(QudiClient):

    name = "dummy"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


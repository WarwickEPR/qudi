from .QudiControl import QudiClient


class DummyClient(QudiClient):

    name = "dummy"

    def __init__(self, *args, **kwargs):
        super(DummyClient, self).__init__(*args, **kwargs)


from .QudiControl import QudiClient


class Dummy(QudiClient):

    name = "dummy"

    def __init__(self, *args, **kwargs):
        super(Dummy, self).__init__(*args, **kwargs)


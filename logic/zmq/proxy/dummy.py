from . base import ZmqProxy
from core.connector import Connector


class DummyProxy(ZmqProxy):

    frontend = Connector(interface='ZmqFrontend')
    confocal = Connector(interface='ConfocalGui')

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)


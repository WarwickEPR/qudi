from tables import *
from . timestamp import get_timestamp

class Psat:

    root = '/psat'
    version = 'Psat_v1.0'

    class Description(IsDescription):
        power = Float32Col(pos=0)
        count_rate = Float32Col(pos=1)

    @classmethod
    def node(cls, tag='', timestamp=None):
        if timestamp is None:
            timestamp = get_timestamp()
        if tag != '':
            return 'psat_{}_{}'.format(tag, timestamp)
        else:
            return 'psat_{}'.format(timestamp)

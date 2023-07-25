from tables import *
from . timestamp import get_timestamp


class Hbt:

    root = '/hbt'
    version = 'HBT_v1.0'

    class Description(IsDescription):
        bin_times = Float32Col(pos=0)
        g2_raw = Float32Col(pos=1)
        g2_raw_normalized = Float32Col(pos=2)

    @classmethod
    def node(cls, tag='', timestamp=None):
        if timestamp is None:
            timestamp = get_timestamp()
        if tag != '':
            return 'hbt_{}_{}'.format(tag, timestamp)
        else:
            return 'hbt_{}'.format(timestamp)

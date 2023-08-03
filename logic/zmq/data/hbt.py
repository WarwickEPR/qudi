from tables import *
from .tables_context import TablesContext
from .base import DataBase


class Hbt(DataBase):

    root = '/hbt'
    stem = 'hbt'
    version = 'HBT_v1.0'

    class Description(IsDescription):
        bin_times = Float32Col(pos=0)
        g2_raw = Float32Col(pos=1)
        g2_normalized = Float32Col(pos=2)

    def __init__(self, tag='', timestamp=None, roi=None, poi=None, bin_times=None, g2_raw=None, g2_normalized=None):
        super(Hbt, self).__init__(tag=tag, timestamp=timestamp, poi=poi, roi=roi)
        self.bin_times = bin_times
        self.g2_raw = g2_raw
        self.g2_normalized = g2_normalized

    def store(self, tc: TablesContext):
        if self.bin_times is None:
            return

        with tc as th:
            dataset = th.create_measurement_table(self.group_path, self.node_name, self.Description)
            dataset.append(list(zip(self.bin_times, self.g2_raw, self.g2_normalized)))
            dataset.attrs['timestamp'] = self.timestamp
            dataset.attrs['tag'] = self.tag
            self._make_poi_link(th.tables, dataset)
            th.flush()

    @classmethod
    def load(cls, tc: TablesContext, node_path: str):
        with tc as th:
            dataset = th.tables.get_node(node_path, classname='Table')
            roi = dataset.attrs.get('roi', None)
            poi = dataset.attrs.get('poi', None)
            bin_times = dataset.read('bin_times')
            g2_raw = dataset.read('g2_raw')
            g2_normalized = dataset.read('g2_normalized')
            tag = dataset.attrs.get('tag', '')
            timestamp = dataset.attrs.get('timestamp', '')
            return Hbt(bin_times=bin_times, g2_raw=g2_raw, g2_normalized=g2_normalized, tag=tag, timestamp=timestamp, roi=roi, poi=poi)

    @classmethod
    def list(cls, tc: TablesContext):
        with tc as th:
            return [x._v_pathname for x in th.tables.iter_nodes(cls.root, classname=Table)]

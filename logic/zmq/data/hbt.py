from tables import *
from .tables_context import TablesContext
from .base import DataBase
import numpy as np


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
            th.flush()

            self.log.info("Saving hbt data to {}:/{}".format(tc.filepath, self.path))
            location = {'file': tc.filepath, 'path': self.path}
            return location

    @classmethod
    def load(cls, tc: TablesContext, node_path: str):
        with tc as th:
            dataset = th.tables.get_node(node_path, classname='Table')

            def get_attr(attr, default):
                try:
                    return dataset._v_attrs[attr]
                except (AttributeError, KeyError):
                    return default

            roi = get_attr('roi', None)
            poi = get_attr('poi', None)
            bin_times = np.array(dataset.read(field='bin_times')).astype(float)
            g2_raw = np.array(dataset.read(field='g2_raw')).astype(float)
            g2_normalized = np.array(dataset.read(field='g2_normalized')).astype(float)
            tag = get_attr('tag', '')
            timestamp = get_attr('timestamp', '')
            return Hbt(bin_times=bin_times, g2_raw=g2_raw, g2_normalized=g2_normalized, tag=tag, timestamp=timestamp, roi=roi, poi=poi)

    @classmethod
    def list(cls, tc: TablesContext):
        with tc as th:
            return [x._v_pathname for x in th.tables.iter_nodes(cls.root, classname=Table)]

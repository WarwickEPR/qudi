from tables import *
from .tables_context import TablesContext
from .base import DataBase
import numpy as np


class Psat(DataBase):

    root = '/psat'
    stem = 'psat'
    version = 'Psat_v1.0'

    class Description(IsDescription):
        power = Float32Col(pos=0)
        count_rate = Float32Col(pos=1)

    def __init__(self, tag='', timestamp=None, roi=None, poi=None, power=None, count_rate=None):
        super(Psat, self).__init__(tag=tag, timestamp=timestamp, poi=poi, roi=roi)
        self.power = power
        self.count_rate = count_rate

    def store(self, tc: TablesContext):
        if self.power is None:
            return

        with tc as th:
            dataset = th.create_measurement_table(self.group_path, self.node_name, self.Description)
            dataset.append(list(zip(self.power, self.count_rate)))
            dataset.attrs['timestamp'] = self.timestamp
            dataset.attrs['tag'] = self.tag
            th.flush()

            self.log.info("Saving psat data to {}:/{}".format(tc.filepath, self.path))
            location = {'file': tc.filepath, 'path': self.path}
            return location

    @classmethod
    def load(cls, tc: TablesContext, node_path: str):

        def get_attr(attr, default):
            try:
                return dataset._v_attrs[attr]
            except (AttributeError, KeyError):
                return default

        with tc as th:
            dataset = th.tables.get_node(node_path, classname='Table')
            roi = get_attr('roi', None)
            poi = get_attr('poi', None)
            power = np.array(dataset.read(field='power')).astype(float)
            count_rate = np.array(dataset.read(field='count_rate')).astype(float)
            tag = get_attr('tag', '')
            timestamp = get_attr('timestamp', '')
            return Psat(power=power, count_rate=count_rate, tag=tag, timestamp=timestamp, roi=roi, poi=poi)

    @classmethod
    def list(cls, tc: TablesContext):
        with tc as th:
            return [x._v_pathname for x in th.tables.iter_nodes(cls.root, classname=Table)]

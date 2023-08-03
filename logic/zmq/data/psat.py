from tables import *
from .tables_context import TablesContext
from .base import DataBase


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
            self._make_poi_link(th.tables, dataset)
            th.flush()

    @classmethod
    def load(cls, tc: TablesContext, node_path: str):
        with tc as th:
            dataset = th.tables.get_node(node_path, classname='Table')
            roi = dataset.attrs.get('roi', None)
            poi = dataset.attrs.get('poi', None)
            power = dataset.read('power')
            count_rate = dataset.read('count_rate')
            tag = dataset.attrs.get('tag', '')
            timestamp = dataset.attrs.get('timestamp', '')
            return Psat(power=power, count_rate=count_rate, tag=tag, timestamp=timestamp, roi=roi, poi=poi)

    @classmethod
    def list(cls, tc: TablesContext):
        with tc as th:
            return [x._v_pathname for x in th.tables.iter_nodes(cls.root, classname=Table)]

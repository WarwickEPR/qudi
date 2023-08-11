import logging

from .timestamp import get_timestamp
import tables
import logging
from time import strptime
from calendar import timegm


class DataBase:

    def __init__(self, tag='', timestamp=None, roi=None, poi=None):
        self.tag = tag
        self.timestamp = timestamp if timestamp is not None else get_timestamp()
        self.roi = roi
        self.poi = poi
        self.log = logging.getLogger('data')

    @classmethod
    def root(cls):
        return cls.root

    @classmethod
    def stem(cls):
        return cls.stem

    @classmethod
    def version(cls):
        return cls.version

    @property
    def node_name(self):
        return '_'.join([self.stem, self.tag, self.timestamp])

    @property
    def path(self):
        return '/'.join([self.root, self.node_name])

    @property
    def group_path(self):
        return self.root

    @property
    def poi_group_path(self):
        if self.poi is not None and self.roi is not None:
            return '/'.join(['/ROI', self.roi, self.poi]) + self.root
        else:
            return None

    @property
    def poi_path(self):
        return '/'.join([self.poi_group_path, self.node_name])

    @staticmethod
    def timestamp_to_epoch_s(ts: str):
        return timegm(strptime(ts, "%Y%m%d_%H%M%S"))

    def _make_poi_link(self, tables: tables, node: tables.Table):
        poi_path = self.poi_group_path
        if poi_path is not None:
            self.log.info("Linking to {}".format(poi_path))
            node._v_attrs['roi'] = self.roi
            node._v_attrs['poi'] = self.poi
            tables.create_hard_link(poi_path, self.node_name, node, createparents=True)


from tables import *
from .tables_context import TablesContext
from .base import DataBase
import numpy as np


class OptimizerImage(DataBase):

    root = '/refocusing/images'
    stem = 'optimizer'
    version = 'OptimizerImage_v1.0'

    # Group with an XY array and a Z line profile. Stores the raw data from the optmizer
    class ZDescription(IsDescription):
        z = Float32Col(pos=0)
        counts = Float32Col(pos=1)

    def __init__(self, tag='', timestamp=None, roi=None, poi=None, xy_data=None, z_data=None, setup=None, fit=None):
        super(OptimizerImage, self).__init__(tag=tag, timestamp=timestamp, poi=poi, roi=roi)
        self.xy_data = xy_data
        self.z_data = z_data
        self.setup = setup
        self.fit = fit

    def store(self, tc: TablesContext):
        if self.xy_data is None:
            return

        with tc as th:
            group = th.tables.create_group(self.group_path, self.node_name, createparents=True)
            z_dataset = th.create_measurement_table(group, 'Z', self.ZDescription)
            z_dataset[:] = self.z_data[0:1, :]
            xy_dataset = th.create_array(group, 'XY', self.xy_data)
            group.attrs['timestamp'] = self.timestamp
            group.attrs['tag'] = self.tag
            group.attrs['version'] = self.version
            for k, v in self.setup:
                group.attrs[k] = v
            for k, v in self.fit:
                group.attrs[k] = v

            self._make_poi_link(th.tables, group)
            th.flush()
            return self.path

    @classmethod
    def load(cls, tc: TablesContext, path: str):
        with tc as th:
            img_group = th.tables.get_node(path, classname='Group')
            roi = img_group.attrs.get('roi', None)
            poi = img_group.attrs.get('poi', None)

            xy_data = np.array(img_group.XY[:])
            z = img_group.Z['z']
            counts = img_group.Z['counts']
            z_data = np.hstack(z.T, counts.T)
            tag = img_group.attrs.get('tag', '')
            timestamp = img_group.attrs.get('timestamp', '')
            setup_keys = ['xy_span', 'z_span', 'xy_resolution', 'z_resolution']
            setup = {}
            for k in setup_keys:
                setup[k] = img_group.attrs['k']
            return OptimizerImage(tag=tag, timestamp=timestamp, roi=roi, poi=poi,
                                  xy_data=xy_data, z_data=z_data, setup=setup)

    @classmethod
    def list(cls, tc: TablesContext):
        with tc as th:
            return [x._v_pathname for x in th.tables.iter_nodes(cls.root, classname=Table)]


class OptimizerTrack:

    root = '/refocusing'
    name = 'track'
    path = '/'.join([root, name])
    version = 'OptimizerTrack'

    class Description(IsDescription):
        roi = StringCol()
        poi = StringCol()
        t = StringCol()  # HDF5 time type compatibility is problematic so store as string
        x = Float32Col()
        y = Float32Col()
        z = Float32Col()
        sigma_x = Float32Col()
        sigma_y = Float32Col()
        sigma_z = Float32Col()
        xy_fitted = BoolCol()
        z_fitted = BoolCol()
        image = StringCol()

    @classmethod
    def record_refocus(cls, tc: TablesContext, optimizer_data: OptimizerImage):

        optimizer_data.store(tc)

        with tc as th:
            try:
                table = th.tables.get_node(cls.path, classname=Table)
            except NoSuchNodeError:
                # create the table
                table = th.tables.create_table(where=cls.root,
                                               name=cls.name,
                                               description=OptimizerTrack,
                                               createparents=True)
            entry = table.row
            entry['roi'] = optimizer_data.roi
            entry['poi'] = optimizer_data.poi
            entry['t'] = optimizer_data.timestamp
            entry['x'] = optimizer_data.fit['x']
            entry['y'] = optimizer_data.fit['y']
            entry['z'] = optimizer_data.fit['z']
            entry['sigma_x'] = optimizer_data.fit['sigma_x']
            entry['sigma_y'] = optimizer_data.fit['sigma_y']
            entry['sigma_z'] = optimizer_data.fit['sigma_z']
            entry['xy_fitted'] = optimizer_data.fit['xy_fitted']
            entry['z_fitted'] = optimizer_data.fit['z_fitted']
            entry['image_path'] = optimizer_data.path
            table.append(entry)
            table.flush()

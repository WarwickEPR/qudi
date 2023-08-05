from numpy.lib.recfunctions import unstructured_to_structured
from tables import *
from .tables_context import TablesContext
from .base import DataBase
import numpy as np
import logging


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
        self.log = logging.getLogger('data.optimizer')
        self.xy_data = xy_data
        self.z_data = z_data
        self.setup = setup
        self.fit = fit
        self.approx_count_rate = 0

        if fit['sigma_x'] and fit['sigma_y'] and fit['sigma_z']:
            # fitted z counts give some indication if this site is still "bright"
            self.approx_count_rate = fit['fitted_z_counts']

    def store(self, tc: TablesContext):
        if self.xy_data is None:
            return

        with tc as th:
            self.log.info("Saving optimizer data to {}".format(self.path))
            group = th.tables.create_group(self.group_path, self.node_name, createparents=True)

            # save xy image
            xy_dataset = th.tables.create_array(group, 'XY', self.xy_data)
            for k in ['x0', 'x1', 'y0', 'y1', 'xy_resolution', 'xy_span']:
                xy_dataset._v_attrs[k] = self.setup.get(k, .0)
            xy_dataset.flush()

            # save z line profile
            z_dataset = th.tables.create_table(group, 'Z', self.ZDescription)
            z_dataset.append(list(zip(self.z_data['z'], self.z_data['counts'])))
            z_dataset._v_attrs['z_resolution'] = self.setup['z_resolution']
            z_dataset._v_attrs['z_span'] = self.setup['z_span']
            z_dataset.flush()

            group._v_attrs['timestamp'] = self.timestamp
            group._v_attrs['tag'] = self.tag
            group._v_attrs['version'] = self.version
            for k, v in self.setup.items():
                group._v_attrs[k] = v
            for k, v in self.fit.items():
                group._v_attrs[k] = v

            self._make_poi_link(th.tables, group)
            th.flush()
            return self.path

    @classmethod
    def load(cls, tc: TablesContext, path: str):
        with tc as th:
            img_group = th.tables.get_node(path, classname='Group')
            roi = img_group._v_attrs.get('roi', None)
            poi = img_group._v_attrs.get('poi', None)

            xy_data = np.array(img_group.XY[:])
            z = img_group.Z['z']
            counts = img_group.Z['counts']
            z_data = unstructured_to_structured(np.hstack(z.T, counts.T), ['z', 'counts'])
            tag = img_group._v_attrs.get('tag', '')
            timestamp = img_group._v_attrs.get('timestamp', '')
            setup_keys = ['xy_span', 'z_span', 'xy_resolution', 'z_resolution']
            setup = {}
            for k in setup_keys:
                setup[k] = img_group._v_attrs[k]
            return OptimizerImage(tag=tag, timestamp=timestamp, roi=roi, poi=poi,
                                  xy_data=xy_data, z_data=z_data, setup=setup)

    @classmethod
    def list(cls, tc: TablesContext):
        with tc as th:
            return [x._v_pathname for x in th.tables.iter_nodes(cls.root, classname="Table")]


class OptimizerTrack:

    root = '/refocusing'
    name = 'track'
    path = '/'.join([root, name])
    version = 'OptimizerTrack'

    class Description(IsDescription):
        roi = StringCol(itemsize=128, pos=0)
        poi = StringCol(itemsize=128, pos=1)
        t = StringCol(itemsize=16, pos=2)  # HDF5 time type compatibility is problematic so store as string
        x = Float32Col(pos=3)
        y = Float32Col(pos=4)
        z = Float32Col(pos=5)
        sigma_x = Float32Col(pos=6)
        sigma_y = Float32Col(pos=7)
        sigma_z = Float32Col(pos=8)
        counts = Float32Col(pos=9)
        xy_fitted = BoolCol(pos=10)
        z_fitted = BoolCol(pos=11)
        image = StringCol(itemsize=512,pos=12)

    @classmethod
    def record_refocus(cls, tc: TablesContext, optimizer_data: OptimizerImage):

        optimizer_data.store(tc)

        with tc as th:
            try:
                table = th.tables.get_node(where=cls.root, name=cls.name, classname="Table")
            except NoSuchNodeError:
                # create the table
                table = th.tables.create_table(where=cls.root,
                                               name=cls.name,
                                               description=OptimizerTrack.Description,
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
            entry['counts'] = optimizer_data.approx_count_rate
            entry['xy_fitted'] = optimizer_data.fit['xy_fitted']
            entry['z_fitted'] = optimizer_data.fit['z_fitted']
            entry['image'] = optimizer_data.path
            entry.append()
            table.flush()

    @classmethod
    def retrieve(cls, tc: TablesContext, roi=None, poi=None):
        with tc as th:
            refocus_track = th.tables.get_node(where=cls.root, name=cls.name, classname='Table')


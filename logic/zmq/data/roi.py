import logging

from tables import *
import numpy as np
from .tables_context import TablesContext
from .timestamp import get_timestamp


class ROI:

    root = '/ROI'
    version = 'ROI_v1.0'

    class Description(IsDescription):
        name = StringCol(128, pos=0)  # limits POI name length but this is ample
        x = Float32Col(pos=1)
        y = Float32Col(pos=2)
        z = Float32Col(pos=3)

    log = logging.getLogger('roi.data')

    def __init__(self, roi_name='', roi_version=None, pois={},
                 origin=(.0, .0, .0), reference_image='', stage_x=.0, stage_y=.0):
        self.roi_name = roi_name
        self.roi_version = roi_version
        self.pois = pois
        self.origin = origin
        self.reference_image = reference_image
        self.stage_x = stage_x
        self.stage_y = stage_y

    @classmethod
    def retrieve(cls, tc: TablesContext, roi_name='', roi_version=None):
        with tc as th:
            try:
                if roi_version is None:
                    # get list of versions
                    versions = [x._v_name for x in th.tables.list_nodes(cls.root, name=roi_name, classname=Table)].sort()
                    roi_version = versions[-1]    # latest by default
                pois = {}
                roi_table = th.tables.get_node('/'.join([cls.root, roi_name]), name=roi_version, classname=Table)
                for poi, x, y, z in roi_table:
                    pois[poi] = x, y, z
                origin = roi_table.attrs.get('origin', (.0, .0, .0))
                reference_image = roi_table.attrs.get('reference_image', '')
                stage_x = roi_table.attrs.get('stage_x', .0)
                stage_y = roi_table.attrs.get('stage_y', .0)
                return ROI(roi_name=roi_name, roi_version=roi_version, pois=pois,
                           origin=origin, reference_image=reference_image, stage_x=stage_x, stage_y=stage_y)

            except NoSuchNodeError:
                # node doesn't exist
                cls.log.warning("Can't retrieve roi '{}' - node doesn't exist")
                return

    def store(self, tc: TablesContext):
        with tc as th:
            if not self.roi_version:
                self.roi_version = get_timestamp()

            with tc as th:
                roi_table = th.tables.create_table('/'.join([self.root, self.roi_name]),
                                                   name=self.roi_version,
                                                   description=self.Description,
                                                   createparents=True)
                pois = [(poi, *self.pois[poi]) for poi in self.pois.keys()]
                roi_table.append(pois)
                roi_table.attrs['roi_name'] = self.roi_name
                roi_table.attrs['origin'] = self.origin if self.origin else (.0, .0, .0)
                roi_table.attrs['reference_image'] = self.reference_image if self.reference_image else ''
                roi_table.attrs['stage_x'] = self.stage_x if self.stage_x else 0.0
                roi_table.attrs['stage_y'] = self.stage_y if self.stage_y else 0.0
                roi_table.flush()


class TiltCorrection:

    def __init__(self, pivot=(0, 0, 0), phi=0, psi=0):
        self.translation = np.array([*pivot])
        self.rotation_x = np.array([[1, 0, 0],
                                    [0, np.cos(phi), -np.sin(phi)],
                                    [0, np.sin(phi), np.cos(phi)]])
        self.rotation_y = np.array([[np.cos(psi), 0, np.sin(psi)],
                                    [0, 1, 0],
                                    [-np.sin(psi), 0, np.cos(psi)]])
        self.rotation = self.rotation_y * self.rotation_x

    def rotate(self, point):

        # translate origin
        p = np.array([*point]) - self.translation

        # apply rotation
        q = self.rotation * p

        # translate origin back
        return q + self.translation


class Rotation:

    def __init__(self, pivot=(0,0), theta=0):
        self.pivot = pivot
        self.theta = theta


class RoiExtract:

    def __init__(self, table: Table):
        self.table = table,

    def pois(self, x_min=-np.inf, x_max=np.inf, y_min=-np.inf, y_max=np.inf, z_min=-np.inf, z_max=np.inf, rotation=None):
        pois = dict()

        for row in self.table:
            x = row['x']
            y = row['y']
            z = row['z']

            if rotation:
                x_orig, y_orig, z_orig = x, y, z
                x, y, z = rotation.rotate(x, y, z)

            if x < x_min: continue
            if x > x_max: continue
            if y < y_min: continue
            if y > y_max: continue
            if z < z_min: continue
            if z > z_max: continue
            pois[row['name]']] = (x, y, z)
        return pois

    # Return a copy rotated into another coordinate system
    def rotate(self, pivot, xy_norm, rotation):
        pass


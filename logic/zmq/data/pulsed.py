import logging

import numpy as np
from tables import *
from . tables_context import TablesContext, TablesHandle
from . timestamp import Timestamp
from . base import DataBase
from tables.exceptions import NodeError, NoSuchNodeError

# a group with raw data and current extraction
# Pulsed/my_measurement_starttime (+attrs) <group>
# Pulsed/my_measurement_starttime/extracted (+attrs) <array>
# Pulsed/my_measurement_starttime/laser (+attrs) <array>
# Pulsed/my_measurement_starttime/raw (+attrs) <array>
# Pulsed/my_measurement_starttime/snapshot/<time>/extracted,laser,raw


class PulsedMeasurement(DataBase):

    root = '/pulsed'
    stem = 'pulsed'
    current = 'latest'
    version = 'Pulsed_v1.1'

    extracted_dtype = [('x', float),
                       ('y', float),
                       ('y_err', float),
                       ('alt', float),
                       ('alt_err', float)]

    class ExtractedDescription(IsDescription):
        variable = Float32Col(pos=0)
        signal = Float32Col(pos=1)
        signal_err = Float32Col(pos=2)
        signal_alt = Float32Col(pos=3)
        signal_alt_err = Float32Col(pos=4)

    @classmethod
    def node(cls, tag='', timestamp=None):
        if timestamp is None:
            timestamp = Timestamp.get_timestamp()
        if tag != '':
            return 'pulsed_{}_{}'.format(tag, timestamp)
        else:
            return 'pulsed_{}'.format(timestamp)

    def __init__(self, tag='', timestamp=None, roi=None, poi=None,
                 measurement='', extracted=None, laser=None, raw=None,
                 predefined_parameters=None, settings=None,
                 update_time=None):
        super(PulsedMeasurement, self).__init__(tag=tag, timestamp=timestamp, poi=poi, roi=roi)
        self._extracted = extracted
        self._laser = laser
        self._raw = raw
        self._measurement = measurement
        self._update_time = update_time
        self._predefined_parameters = predefined_parameters
        self._settings = settings

    @property
    def node_name(self):
        return '_'.join([self._measurement, self.tag, self.timestamp])

    def _save_snapshot(self, group):
        snapshot_name = 'snapshot_' + Timestamp.get_timestamp()
        try:
            # copy current to snapshot_<timestamp> under this path
            group._f_copy(newparent=self.path, newname=snapshot_name, createparents=True, recursive=True)
            self.log.info("Saved snapshot of pulsed measurement to {}".format(snapshot_name))
        except (NodeError, TypeError):
            self.log.error("Failed to copy snapshot from {} to {}".format(self.path, snapshot_name))

    def _create_measurement_group(self, th: TablesHandle, group_path):
        group = th.tables.create_group(group_path, self.current, createparents=True)
        self.log.info("Created pulsed measurement group {}".format(self.path))
        th.flush()
        if self.poi and self.roi:
            link_group = '/'.join(['/ROI', self.roi, self.poi, self.group_path])
            self.log.info("Linking {}/{} to {}".format(link_group, self.node_name, self.path))
            #th.tables.create_hard_link(self.group_path, self.node_name, link_group + '/' + self.node_name, createparents=True)
        return group

    def _get_measurement_group(self, th: TablesHandle, snapshot=False):
        # get the group node where the measurements are stored under "latest"
        # copy into a snapshot sibling group

        current_group = '/'.join([self.path, self.current])

        # /pulsed/<measurement>_<tag>_<timestamp>/current as group
        # containing extracted, laser, raw
        update = False

        try:
            group = th.tables.get_node(current_group, classname='Group')
            self.log.info("Found pulsed measurement group {}".format(self.path))
            update = True

        except NoSuchNodeError:
            # not yet created, create the group and link it to POI
            group = self._create_measurement_group(th, self.path)

        return group, update

    @classmethod
    def extracted_from_fields(cls, x, y, y_err, alt=None, alt_err=None):
        if alt is None:
            alt = np.zeros_like(x)
        if alt_err is None:
            alt_err = np.zeros_like(x)
        return np.fromiter(zip(x, y, y_err, alt, alt_err), dtype=cls.extracted_dtype)

    @staticmethod
    def _set_attrs(node: Node, params: dict, prefix=''):
        for k, v in params.items():
            node._v_attrs[prefix + k] = v

    @staticmethod
    def _get_attrs(node: Node, prefix=''):
        params = {}
        for attr in node._v_attrs._f_list():
            if attr.startswith(prefix):
                k = attr[len(prefix):]
                params[k] = node._v_attrs[attr]
        return params

    def store(self, tc: TablesContext, snapshot=False):
        with tc as th:
            try:
                group, update = self._get_measurement_group(th, snapshot)
                group._v_attrs['measurement'] = self._measurement if self._measurement else ''
                group._v_attrs['tag'] = self.tag
                group._v_attrs['roi'] = self.roi if self.roi else ''
                group._v_attrs['poi'] = self.poi if self.poi else ''
                self._set_attrs(group, self._predefined_parameters, prefix='predefined_')
                self._set_attrs(group, self._settings, prefix='settings_')

                # mark the last update time
                group._v_attrs['update_time'] = Timestamp.get_timestamp()

                # Update or create extracted table
                try:
                    extracted = group.extracted
                    self.log.info("Updating extracted table")
                except NoSuchNodeError:
                    extracted = th.tables.create_table(group, 'extracted', description=self.ExtractedDescription)
                    self.log.info("Created extracted table")
                extracted.remove_rows()
                extracted.append(self._extracted)
                self.log.info("Updated extracted table, {} rows".format(self._extracted.shape[0]))

                try:
                    laser = group.laser
                    self.log.info("Updating laser array")
                    laser[...] = self._laser
                    self.log.info("Updated laser array")
                except NoSuchNodeError:
                    laser = th.tables.create_array(group, 'laser', self._laser)
                    self.log.info("Created laser array {}".format(self._laser.shape))

                # same for raw
                try:
                    raw = group.raw
                    self.log.info("Updating raw array")
                    raw[...] = self._raw
                    self.log.info("Updated raw array")
                except NoSuchNodeError:
                    raw = th.tables.create_array(group, 'raw', self._raw)
                    self.log.info("Created raw array {}".format(self._raw.shape))

                if update and snapshot:
                    self._save_snapshot(group)


            except NodeError:
                self.log.exception("Failed to save pulsed experiment {}".format(self.path))

        return {'file': tc.filepath, 'path': self.path}

    @classmethod
    def load(cls, tc: TablesContext, path: str, snapshot=None):
        logger = logging.getLogger('PulsedData')
        with tc as th:
            try:
                if snapshot is None:
                    snapshot = cls.current
                group = th.get_node(path, snapshot)
                try:
                    predefs = cls._get_attrs(group, prefix='predefined_')
                    settings = cls._get_attrs(group, prefix='settings_')
                    update_time = group._v_attrs['update_time']
                    measurement = group._v_attrs['measurement']
                    tag = group._v_attrs['tag']
                    roi = group._v_attrs['roi']
                    poi = group._v_attrs['poi']
                except AttributeError:
                    logger.warning("Could not load attributes of group {}".format(path))
                try:
                    extracted = group.extracted.read().astype(cls.extracted_dtype)
                    raw = np.array(group.raw[:])
                    laser = np.array(group.laser[:])

                    return PulsedMeasurement(tag=tag, measurement=measurement, roi=roi, poi=poi,
                                             extracted=extracted, raw=raw, laser=laser,
                                             predefined_parameters=predefs, settings=settings,
                                             update_time=update_time)
                except NodeError as e:
                    logger.error("Failed to load data for group {}: {}".format(path, e))

            except NoSuchNodeError:
                logger.error("Can't find {}/{}".format(path, snapshot))

    @classmethod
    def list_measurements(cls, tc: TablesContext, prefix=None, roi=None, poi=None):
        with tc as th:
            if poi is None:
                measurements = th.tables.list_nodes(cls.root)
            else:
                measurements = th.tables.list_nodes('/'.join(['/ROI', roi, poi]))
            if prefix is not None:
                measurements = [filter(lambda x: x.startswith(prefix), measurements)]
            return measurements

    # snapshots of current measurement
    @classmethod
    def list_snapshots(cls, tc: TablesContext, measurement_path: str):
        with tc as th:
            return [filter(lambda x: x.startswith('snapshot'), th.tables.list_nodes(measurement_path))]

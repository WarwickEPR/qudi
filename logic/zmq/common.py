from enum import Enum
import filelock
import tables
import time

# Used by both Qudi and client side of ZMQ based remoting system


class Orientation(Enum):
    XY = 0
    XZ = 1
    YZ = 2


def abbreviate_frames(frames):
    return "{} bytes".format(sum(len(x) for x in frames))


class TablesHandle:

    def __init__(self, handle: tables.File, logger=None, active_poi=None):
        self.tables = handle
        self.logger = logger
        self._active_poi = active_poi

    def close(self):
        self.tables.close()
        self.tables = None

    def flush(self):
        self.tables.flush()

    @property
    def filepath(self):
        return self.tables.filename

    @classmethod
    def timestamp(cls):
        return time.strftime("%Y%m%d_%H%M%S", time.gmtime())

    @property
    def poi(self):
        return self._active_poi if self._active_poi is not None else '_'

    @property
    def use_poi(self):
        return self._active_poi is not None

    def dataset_site_folder(self, measurement):
        # to hard link this dataset to for convenience e.g. /site/poi-99/psat/20211225090059
        return '/'.join(['', 'site', self.poi, measurement])

    def dataset_path(self, folder, prefix=None, timestamp=None):
        if timestamp is None:
            timestamp = self.timestamp()
        if prefix is None:
            path = [folder, timestamp]
        else:
            path = [folder, prefix, timestamp]

        # to hard link this dataset to for convenience e.g. /psat/20211225090059 or /psat/20220101004929
        return '/'.join(['', folder]), '_'.join(path)

    def create_measurement_table(self, measurement, data_format):
        folder, dataset_name = self.dataset_path(measurement)
        dataset = self.tables.create_table(folder, dataset_name, description=data_format, createparents=True)
        if self.logger:
            self.logger.info("Created table {}".format(dataset._v_pathname))
        if self.use_poi:
            # Link the dataset under the site also
            self.link_to_site(measurement, dataset_name, dataset)
        return dataset

    def create_array(self, measurement, data):
        folder, dataset_name = self.dataset_path(measurement)
        dataset = self.tables.create_array(folder, dataset_name, data, createparents=True)
        if self.logger:
            self.logger.info("Created array {}".format(dataset._v_pathname))
        # Link the dataset under the site also
        if self.use_poi:
            self.link_to_site(measurement, dataset_name, dataset)
        return dataset

    def create_group(self, measurement, prefix=None):
        folder, group_name = self.dataset_path(measurement)
        group = self.tables.create_group(folder, group_name, createparents=True)
        if self.logger:
            self.logger.info("Created group {}".format(group._v_pathname))
        # Link the dataset under the site also
        if self.use_poi:
            self.link_to_site(measurement, group_name, group)
        return group

    def link_to_site(self, measurement, name, node):
        if self.use_poi:
            site_folder = self.dataset_site_folder(measurement)
            if self.logger:
                self.logger.info("Linking {}/{} to {}".format(site_folder, name, node._v_pathname))
            self.tables.create_hard_link(site_folder, name, node, createparents=True)


class TablesContext:

    def __init__(self, filepath, writable=False, timeout=10, logger=None, active_poi=None):
        self.filepath = filepath
        self.mode = 'a' if writable else 'r'
        self.timeout = timeout
        self.logger = logger
        self._active_poi = active_poi

    def __enter__(self):
        # give the caller a handle to an .h5 archive
        # lock access with a file so. notebooks can access safely whilst running
        # Might not be necessary if SWMR was implemented in PyTables
        # As that's the case, only open the file to use it to avoid blocking access
        try:
            with filelock.FileLock(self.filepath + '.lock', timeout=self.timeout):

                try:
                    th = tables.open_file(self.filepath, mode=self.mode)
                    self.tables_handle = TablesHandle(th, logger=self.logger, active_poi=self._active_poi)
                    return self.tables_handle
                except Exception as e:
                    if self.logger:
                        self.logger.warning("Exception opening {} {}".format(self.filepath, repr(e)))
                    raise e

        except filelock.Timeout as e:
            if self.logger:
                self.logger.warning("Attempt to acquire lock on {} timed out".format(self.filepath))
            raise e

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.tables_handle.close()

    @classmethod
    def timestamp(cls):
        return time.strftime("%Y%m%d_%H%M%S", time.gmtime())

    @classmethod
    def dataset_site_folder(cls, site, measurement):
        # to hard link this dataset to for convenience e.g. /site/poi-99/psat/20211225090059
        return '/'.join(['', 'site', site, measurement])

    @classmethod
    def dataset_path(cls, folder, timestamp=None, site=None):
        if timestamp is None:
            timestamp = cls.timestamp()
        if not site:
            site = '_'
        # to hard link this dataset to for convenience e.g. /psat/20211225090059 or /psat/20220101004929
        return '/'.join(['', folder]), '_'.join([folder, timestamp])

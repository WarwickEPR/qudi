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

    def __init__(self, handle: tables.File, logger=None):
        self.tables = handle
        self.logger = logger

    def close(self):
        self.tables.close()
        self.tables = None

    def flush(self):
        self.tables.flush()

    @property
    def filepath(self):
        return self.tables.filename

    def create_measurement_table(self, measurement, data_format, poi=None):
        folder, dataset_name = TablesContext.dataset_path(measurement, site=poi)
        dataset = self.tables.create_table(folder, dataset_name, description=data_format, createparents=True)
        if self.logger:
            self.logger.info("Created table {}".format(dataset._v_pathname))
        if poi:
            # Link the dataset under the site also
            self.link_to_site(poi, measurement, dataset_name, dataset)
        return dataset

    def create_array(self, measurement, data, poi=None):
        folder, dataset_name = TablesContext.dataset_path(measurement, site=poi)
        dataset = self.tables.create_array(folder, dataset_name, data, createparents=True)
        if self.logger:
            self.logger.info("Created array {}".format(dataset._v_pathname))
        # Link the dataset under the site also
        if poi:
            # Link the dataset under the site also
            self.link_to_site(poi, measurement, dataset_name, dataset)
        return dataset

    def create_group(self, measurement, poi=None):
        folder, group_name = TablesContext.dataset_path(measurement, site=poi)
        group = self.tables.create_array(folder, group_name, createparents=True)
        if self.logger:
            self.logger.info("Created group {}".format(group._v_pathname))
        # Link the dataset under the site also
        if poi:
            # Link the dataset under the site also
            self.link_to_site(poi, measurement, group_name, group)
        return group

    def link_to_site(self, site, measurement, name, node):
        site_folder = TablesContext.dataset_site_folder(site, measurement)
        if self.logger:
            self.logger.info("Linking {}/{} to {}".format(site_folder, name, node._v_pathname))
        self.tables.create_hard_link(site_folder, name, node, createparents=True)


class TablesContext:

    def __init__(self, filepath, writable=False, timeout=10, logger=None):
        self.filepath = filepath
        self.mode = 'a' if writable else 'r'
        self.timeout = timeout
        self.logger = logger

    def __enter__(self):
        # give the caller a handle to an .h5 archive
        # lock access with a file so notebooks can access safely whilst running
        # Might not be necessary if SWMR was implemented in PyTables
        # As that's the case, only open the file to use it to avoid blocking access
        try:
            with filelock.FileLock(self.filepath + '.lock', timeout=self.timeout):

                try:
                    th = tables.open_file(self.filepath, mode=self.mode)
                    self.tables_handle = TablesHandle(th, logger=self.logger)
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

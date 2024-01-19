import filelock
import tables
from tables import NoSuchNodeError

from . timestamp import Timestamp


class TablesHandle:

    def __init__(self, handle: tables.File, logger=None, active_poi=None, active_roi=None):
        self.tables = handle
        self.logger = logger
        self._active_roi = active_roi
        self._active_poi = active_poi

    def close(self):
        if self.tables:
            self.tables.close()
        self.tables = None

    def flush(self):
        self.tables.flush()

    @property
    def filepath(self):
        return self.tables.filename

    def list(self, root='/', data_type_prefix='', **kwargs):

        def filter_nodes(n):
            if data_type_prefix:
                try:
                    if not n.attrs.data_type.startswith(data_type_prefix):
                        return False
                except AttributeError:
                    return False
            return True

        try:
            n = self.tables.get_node(root)
            yield from filter(filter_nodes, self.tables.walk_nodes(root, **kwargs))
        except NoSuchNodeError:
            pass

    def list_concise(self, **kwargs):
        return map(lambda x: x._v_pathname, self.list(**kwargs))

    def get(self, where='/'):
        node = self.tables.get_node(where=where)
        return node

    @property
    def poi(self):
        return self._active_poi if self._active_poi is not None else '_'

    @property
    def roi(self):
        return self._active_roi if self._active_roi is not None else '_'

    @property
    def use_poi(self):
        return self._active_poi is not None

    # Add these as helpers but create whatever data structures required using the timestamps to label
    # If a measurement is related to a POI then it can be linked additionally under the POI name
    def create_measurement_table(self, group, entry_name, description):
        dataset = self.tables.create_table(group, entry_name, description=description, createparents=True)
        if self.logger:
            self.logger.info("Created table {}".format(dataset._v_pathname))
        if self.use_poi:
            # Link the dataset under the site also
            self.link_to_poi(dataset)
        return dataset

    def create_array(self, group, entry_name, data, data_type: str):
        dataset = self.tables.create_array(group, entry_name, data, createparents=True)
        dataset.attrs.data_type = data_type
        if self.logger:
            self.logger.info("Created {} array {}".format(data_type, dataset._v_pathname))
        # Link the dataset under the site/roi also
        if data_type.startswith("Image"):
            self.link_to_roi(dataset)
        elif self.use_poi:
            self.link_to_poi(dataset)
        return dataset

    def link_to_poi(self, node):
        if self.use_poi:
            if isinstance(node, str):
                node = self.tables.get_node(node)
            node_group = self.tables.get_node(node._v_parent)._v_pathname
            node_name = node._v_name
            link_group = '/ROI/{}/{}{}'.format(self.roi, self.poi, node_group)
            if self.logger:
                self.logger.info("Linking {}/{} to {}".format(link_group, node_name, node._v_pathname))
            self.tables.create_hard_link(link_group, node_name, node, createparents=True)

    def link_to_roi(self, node):
        if self.use_poi:
            node_group = node._v_parent._v_pathname
            node_name = node.name
            link_group = '/ROI/{}{}'.format(self.roi, node_group)
            if self.logger:
                self.logger.info("Linking {}/{} to {}".format(link_group, node_name, node._v_pathname))
            self.tables.create_hard_link(link_group, node_name, node, createparents=True)


class TablesContext:

    def __init__(self, filepath, writable=False, timeout=10, logger=None, active_poi=None, active_roi=None):
        self.filepath = filepath
        self.mode = 'a' if writable else 'r'
        self.timeout = timeout
        self.logger = logger
        self._active_poi = active_poi
        self._active_roi = active_roi

    def __enter__(self):
        # give the caller a handle to an .h5 archive
        # lock access with a file so. notebooks can access safely whilst running
        # Might not be necessary if SWMR was implemented in PyTables
        # As that's the case, only open the file to use it to avoid blocking access
        try:
            with filelock.FileLock(self.filepath + '.lock', timeout=self.timeout):

                try:
                    th = tables.open_file(self.filepath, mode=self.mode)
                    self.tables_handle = TablesHandle(th,
                                                      logger=self.logger,
                                                      active_roi=self._active_roi,
                                                      active_poi=self._active_poi)
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

    @staticmethod
    def timestamp():
        return Timestamp.get_timestamp()

    # @classmethod
    # def dataset_site_folder(cls, site, measurement):
    #     # to hard link this dataset to for convenience e.g. /site/poi-99/psat/20211225090059
    #     return '/'.join(['', 'site', site, measurement])
    #
    # @classmethod
    # def dataset_path(cls, folder, timestamp=None, site=None):
    #     if timestamp is None:
    #         timestamp = cls.timestamp()
    #     if not site:
    #         site = '_'
    #     # to hard link this dataset to for convenience e.g. /psat/20211225090059 or /psat/20220101004929
    #     return '/'.join(['', folder]), '_'.join([folder, timestamp])

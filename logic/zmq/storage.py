import tables
from logic.generic_logic import GenericLogic
from core.configoption import ConfigOption
from core.connector import Connector
import os.path
from . data.tables_context import TablesContext


class NoDataFileSpecified(Exception):
    pass


# Acts as a connectable logic module giving access to any currently attached HDF5 file as a TablesContext
# HDF5 doesn't allow concurrent access unfortunately so TablesContext provides a Python context which controls
# access with a lock to give a TablesHandle

class TablesStorage(GenericLogic):

    # local disk location for efficient, robust storage
    base_directory = ConfigOption('base_directory', 'session_data')

    poimanager = Connector(interface='PoiManagerLogic')

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)
        self.data_file = None
        self.data_title = ''
        self._base_directory = str(self.base_directory)
        if not os.path.isdir(self._base_directory):
            os.mkdir(self._base_directory)

    def on_activate(self):
        self.log.info("Using local base directory {} for working .h5 files".format(self._base_directory))

    def on_deactivate(self):
        pass

    # start a new session and ensure we have an archive file
    # don't keep it open though as .h5 doesn't like concurrent access
    def attach_data_file(self, file=None, title=''):
        if title:
            self.data_title = title
        if file:
            # path relative to base
            self.data_file = file
        if not os.path.isfile(self.data_file):
            # create .h5 file if it doesn't exist
            self.log.debug("Creating HDFS5 file: {}".format(self.data_file))
            t = tables.open_file(self.data_file, mode='w', title=self.data_title)
            t.close()
        else:
            self.log.debug("{} already exists".format(self.data_file))

    def detach_data_file(self):
        # just to ensure no-one elese appends to this data file
        self.data_file = None

    def attached(self):
        if self.data_file:
            return True
        else:
            return False

    def tables_context(self, use_poi=True):
        roi = self.poimanager().roi_name
        poi = self.poimanager().active_poi if use_poi else None
        return TablesContext(self.data_file_path, writable=True, logger=self.log, active_poi=poi, active_roi=roi)

    @property
    def data_file_path(self):
        if not self.data_file:
            raise NoDataFileSpecified()
        return os.path.join(self._base_directory, self.data_file)

import tables
from logic.generic_logic import GenericLogic
from core.configoption import ConfigOption
import os.path
from logic.zmq.common import TablesContext


class TablesStorage(GenericLogic):

    # local disk location for efficient, robust storage
    local_directory = ConfigOption('local_directory', 'session_data')
    # remote file server location
    filer_directory = ConfigOption('shared_directory', '', missing='warn')

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)
        self.session_name = 'session-' + self.timestamp()
        self.session_title = ''
        self._local_directory = str(self.local_directory)
        self._filer_directory = str(self.filer_directory)
        if not os.path.isdir(self._local_directory):
            os.mkdir(self._local_directory)

    def on_activate(self):
        self.log.info("Using local directory {} for working .h5 files".format(self._local_directory))

    def on_deactivate(self):
        pass

    # start a new session and ensure we have an archive file
    # don't keep it open though as .h5 doesn't like concurrent access
    def open_session(self, name=None, title=''):
        if name:
            self.session_name = name
        if title:
            self.session_title = title
        if not os.path.isfile(self.local_filepath):
            # create .h5 file if it doesn't exist
            self.log.debug("Creating HDFS5 file: {}".format(self.local_filepath))
            t = tables.open_file(self.local_filepath, mode='w', title=self.session_title)
            t.close()
        else:
            self.log.debug("{} already exists".format(self.local_filepath))

    @staticmethod
    def timestamp():
        return TablesContext.timestamp()

    def close_session(self):
        # just to ensure the session name isn't reused by someone else
        self.session_name = 'session-' + self.timestamp()

    def tables_context(self):
        return TablesContext(self.local_filepath, writable=True, logger=self.log)

    @property
    def local_filepath(self):
        return os.path.join(self._local_directory, self.session_name + ".h5")

    @property
    def shared_filepath(self):
        return os.path.join(self._filer_directory, self.session_name + ".h5")


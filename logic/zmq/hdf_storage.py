import shutil
import logging

from core.configoption import ConfigOption
from core.util.mutex import Mutex
from logic.generic_logic import GenericLogic
from pathlib import PurePath
from contextlib import contextmanager
from datetime import datetime

# Keeps track of the current series of measurement's HDF5 data store
# Allows other modules to just use "the current data store" to store data
# and ensures that only one thread is actually writing to the HDF file

import h5py


class HdfHandle:

    def __init__(self, handle):
        self.handle = handle
        self.log = logging.getLogger('{}.{}'.format(self.__module__, self.__class__.__name__))

    def __enter__(self):
        return self.handle

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.log.warning("Hdf Exception: {} {} {}".format(exc_type, exc_val, exc_tb))
        self.handle.file.close()


class HdfStorage(GenericLogic):

    # local disk location for efficient, robust storage
    localDirectory = ConfigOption('local_directory', 'session_data')
    # remote file server location
    remoteDirectory = ConfigOption('remote_directory', '', missing='warn')

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)
        self._session = 'session-' + self.timestamp()
        self._local_directory = str(self.localDirectory)
        self._remote_directory = str(self.remoteDirectory)
        self.lock = Mutex()

    def on_activate(self):
        pass

    def on_deactivate(self):
        pass

    @classmethod
    def timestamp(cls):
        return datetime.now().strftime("%Y%m%d-%H%M%S")

    @property
    def session(self):
        return self._session

    @session.setter
    def session(self, name):
        self._session = name

    @property
    def local_directory(self):
        return self._local_directory

    @local_directory.setter
    def local_directory(self, directory):
        self._local_directory = directory

    @property
    def remote_directory(self):
        return self._remote_directory

    @remote_directory.setter
    def remote_directory(self, directory):
        self._remote_directory = directory

    def local_filepath(self):
        return PurePath(self._local_directory, self._session + '.hdf5')

    # return an HDF5 file object as an abstract context for us in "with" blocks which will close on exit/exception
    # e.g. with storage().handle() as f:
    #          ....
    # Use a mutex to ensure that only one writer accesses the archive at once, at least in this process
    # Use SWMR to allow clients to read data concurrently to writing, but close after each operation in any case
    # h5py claims to be thread safe with a global lock so other threads should be able to use these methods to get
    # handles to HFS5 groups without moving the handle between thread context
    @contextmanager
    def hdf_file(self):
        with self.lock:
            try:
                f = h5py.File(name=self.local_filepath(), mode='a', libver='latest')
                f.swmr_mode = True
            except Exception as e:
                raise e

            try:
                yield f
            finally:
                f.close()

    # Yields a timestamped subgroup for storing measurement data of a particular type
    # Optionally also link to a particular site/POI
    @contextmanager
    def folder(self, measurement, site=None, timestamp=None):

        # store multiple measurements of the same thing by using a timestamp as a unique key
        if timestamp is None:
            timestamp = self.timestamp()

        with self.hdf_file() as hdf:

            # get a "directory" to put this data in
            # e.g. /image/site-C or /image
            if site:
                # so something like /psat/poi-99
                g = hdf.require_group('/'.join(['', measurement, site]))
                # hard link this also to e.g. /site/poi-99/psat
                hdf['/'.join(['/site', site, measurement])] = g
            else:
                # not an assigned POI site (e.g. for images or unassigned)
                # path something like: /confocal
                g = hdf.require_group('/'.join(['', measurement]))

            if timestamp not in g:
                self.log.debug("Creating group {} under {}".format(timestamp, g.name))

            yield g.require_group(timestamp)

    @classmethod
    def dataset_site_path(cls, site, measurement, timestamp=None):
        if timestamp is None:
            timestamp = cls.timestamp()
        # to hard link this dataset to for convenience e.g. /site/poi-99/psat/20211225090059
        return '/'.join(['', 'site', site, measurement, timestamp])

    @classmethod
    def dataset_path(cls, folder, timestamp=None, site=None):
        if timestamp is None:
            timestamp = cls.timestamp()
        if site is None:
            site = '_'
        # to hard link this dataset to for convenience e.g. /psat/poi-99/20211225090059 or /psat/_/20220101004929
        return '/'.join(['', folder, site, timestamp])

    def copy_to_remote(self):
        if self.remote_directory:
            # ensure no-one is writing
            self.lock.lock()
            shutil.copyfile(self.local_filepath(), self.remote_directory)
            self.lock.unlock()

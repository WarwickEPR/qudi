import h5py
import time


class DataStore:

    def __init__(self, filename, prefix=None):
        try:
            # open in SWMR mode to allow readers at same time as writing consistently
            # allowing online processing of results from file
            # Ask for the latest version (rather than most compatible) to ensure features such as
            # SWMR are available
            self.storage = h5py.File(filename, 'a', libver='latest')
            self.storage.swmr_mode = True

            if prefix:
                self._root = self.storage.require_group(prefix)
            else:
                self._root = self.storage

        except Exception as e:
            # Mapped from underlying HDFS but not documented
            # self.log.error("Exception opening HDF file: {}".data(e))
            raise e

    # Use my_store.root to access the
    @property
    def root(self):
        return self._root

    # possibly add helpers in here later but the HDF5 API is pretty straightforward

    # Get a HDF5 group object to put a measurement in (like a Python dict of data)
    # Set up structure here so it's reasonably consistent
    #
    # Multiple NumPy array-like datasets from one measurement can be put in this folder
    # such as raw pulse data + extracted data
    # e.g. d = ds.folder('hahn-echo', 'site-A')
    #      d["raw"] = raw_data
    #      d["extracted"] = extracted
    #
    # data can also be annotated with associated parameters
    #      d.attrs['rabi-period'] = 100e-9
    #      d["extracted"].attrs['extraction-window'] = [0, 150e-9]
    #
    # This location can also be used later for analysis output e.g. fitted parameters or plotted images
    def measurement_folder(self, measurement, site=None, timestamp=None):

        # easy way to allow for multiple measurements of the same thing
        if timestamp is None:
            timestamp = time.strftime("%Y%m%d-%H%M%S")

        # get a "directory" to put this data in
        # e.g. /image/site-C or /image
        if site:
            # so something like /psat/poi-99
            g = self.storage.require_group('/'.join(['', measurement, site]))
            # hard link this also to e.g. /site/poi-99/psat
            self.storage['/'.join(['/site', site, measurement])] = g
        else:
            # no POI site (e.g. for images or unassigned)
            # path something like: /confocal
            g = self.storage.require_group('/'.join(['', measurement]))

        return g.create_group(timestamp)

    def __del__(self):
        # "hard close" the HDF5 file which will invalidate any handles to it
        self.storage.close()

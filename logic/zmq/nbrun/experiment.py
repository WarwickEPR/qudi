import logging

from .track import Track
from .wait import InterruptableWaitManager, InterruptableWaitHandle
from asyncio import CancelledError
from logic.zmq.client import *
from .. data.tables_context import TablesContext
from .. data.psat import Psat as PsatData
from .. data.hbt import Hbt as HbtData
from .. data.optimizer import OptimizerTrack, OptimizerImage
from .. client.optimizer import RefocusFailed, ZRefocusFailed
import asyncio
from . track import TrackProgress
from ipywidgets import Output
from IPython.display import display

import matplotlib.pyplot as plt
import matplotlib
import numpy as np

from ..display.optimizer import RefocusDisplay


# wrap up all the setup conveniently


class AbortExperiment(Exception):
    def __init__(self, msg=''):
        self.msg = msg

    def __repr(self):
        if self.msg:
            return "Experiment abort: {}".format(self.msg)
        else:
            return "Experiment abort"


class RefocusWentDark(RefocusFailed):
    pass


class RefocusOutOfBounds(RefocusFailed):
    pass

# Effectively a singleton for each sub notebook kernel, just for convenience of bundling up setup


class Experiment:

    run_name = ''
    track: Track = None
    iwm: InterruptableWaitManager = None
    qc: QudiControl = None
    tables_context: TablesContext = None

    @classmethod
    def apply_log_exclusions(cls):
        for l in ['Comm', 'matplotlib']:
            log = logging.getLogger(l)
            log.setLevel(logging.INFO)

    @classmethod
    async def setup(cls, name='anon_experiment', hdf5_file=None, poi=None):
        cls.run_name = "{}_{}".format(name, poi)
        logging.basicConfig(filename="logs/{}.log".format(cls.run_name), filemode="w", level=logging.DEBUG)
        cls.apply_log_exclusions()
        matplotlib.use('agg')    # for non-interactive plot widgets, better for avoiding matplotlib memory leaks?
        stop_file = cls.run_name + ".stop"
        cls.track = Track.setup()
        cls.iwm = InterruptableWaitManager(stop_file=stop_file, tracker=cls.track)
        cls.qc = QudiControl()
        if hdf5_file:
            await cls.qc.manager.attach_data_file(hdf5_file)
            cls.tables_context = TablesContext(hdf5_file)
        else:
            cls.qc.log.warning("No HDF5 file attached: you should probably set hdf5_file if storing data")

    @classmethod
    def expand_parameters(cls, pois: list, name: str, hdf5_file: str, additional=None):
        if additional is None:
            additional = {}
        params = {}
        for poi in pois:
            params[poi] = additional.copy()
            params[poi].update({'poi': poi,
                                'name': name,
                                'hdf5_file': hdf5_file})
        return params

    @classmethod
    async def setup_top(cls, name="anon", hdf5_file=None):
        cls.run_name = "{}_runner".format(name)
        logging.basicConfig(filename="logs/{}.log".format(cls.run_name), filemode="w", level=logging.DEBUG)
        cls.apply_log_exclusions()
        matplotlib.use('agg')    # for non-interactive plot widgets, better for avoiding matplotlib memory leaks?
        cls.qc = QudiControl()
        if hdf5_file:
            await cls.qc.manager.attach_data_file(hdf5_file)
            cls.tables_context = TablesContext(hdf5_file)
        else:
            cls.qc.log.warning("No HDF5 file attached: you should probably set hdf5_file if storing data")


class Refocus:

    # make an instance to hold an output
    def __init__(self, min_count_threshold=np.inf):
        self._display_output = Output()
        self.min_count_threshold = min_count_threshold
        self._display = RefocusDisplay(Experiment.tables_context, Experiment.qc)
        # start a background async task to listen for saving
        self._display.update_on_save(handler=self.update_latest)

    def display_latest(self):
        return self._display_output

    def update_latest(self):
        self._display_output.outputs = []
        self._display_output.append_display_data(self._display.latest_fig)

    async def refocus(self, poi=None, refine_poi=False, settings=None, min_count_threshold=None):
        min_count_threshold = min_count_threshold if min_count_threshold is not None else self.min_count_threshold
        if settings is not None:
            # e.g. to set span of optimizer image appropriately
            Experiment.qc.optimizer.setup(settings)
        refocus_done = Experiment.qc.optimizer.pending_refocus()
        if poi is not None:
            await Experiment.qc.poimanager.set_active_poi(poi)
            await Experiment.qc.poimanager.goto_poi()
            await asyncio.sleep(1)
        await Experiment.qc.optimizer.refocus()
        try:
            aw = self._result(refocus_done, min_count_threshold)
            x, y, z = await Experiment.iwm.wait_for(aw, 'refocus')
            if poi is not None:
                if refine_poi:
                    await Experiment.qc.poimanager.update_poi_position()
                else:
                    await Experiment.qc.poimanager.update_roi_position()
            return x, y, z
        except CancelledError:
            await Experiment.qc.optimizer.stop_refocus()
            raise

    @classmethod
    async def _result(cls, refocus_done, min_count_threshold):
        refocus_result = await refocus_done
        xy_fitted = refocus_result.get('xy_fitted', False)
        z_fitted = refocus_result.get('z_fitted', False)
        if xy_fitted and z_fitted:
            # add heuristics
            # are the max counts reasonable
            try:
                if refocus_result['fitted_counts'] < min_count_threshold:
                    raise RefocusWentDark
                if not refocus_result['in_bounds']:
                    raise RefocusOutOfBounds
            except KeyError:
                print("Warning: missing information about refocus")

            return refocus_result['x'], refocus_result['y'], refocus_result['z']
        else:
            if not z_fitted and xy_fitted:
                raise ZRefocusFailed
            else:
                raise RefocusFailed

    @classmethod
    async def save(cls):
        return await Experiment.qc.optimizer.save_hdf5()

    @classmethod
    def load(cls, path):
        return OptimizerImage.load(Experiment.tables_context, path)

class Hbt:

    @staticmethod
    async def run(time=300):
        done = Experiment.qc.hbt.pending_done()
        await Experiment.qc.hbt.start_timed(time=time)
        await Experiment.iwm.wait_for(done, 'Hbt')

    @staticmethod
    async def save():
        # ask the Qudi end to save the data
        hdf5_location = await Experiment.qc.hbt.save_hdf5()
        qudi_path = await Experiment.qc.hbt.save_qudi()
        return hdf5_location

    @staticmethod
    def load(path):
        # retrieve the data from HDF5 - ensuring we know we actually have it stored!
        return HbtData.load(Experiment.tables_context, path)



class Psat:

    @staticmethod
    async def take_psat():
        fitted = Experiment.qc.aom.pending_psat_fit()
        await Experiment.qc.aom.take_psat()
        fit = await Experiment.iwm.wait_for(fitted, 'Psat')
        print('Psat fit received: {}'.format(fit))
        return fit

    @staticmethod
    async def save():
        # ask the Qudi end to save the data
        hdf5_location = await Experiment.qc.aom.save_hdf5()
        qudi_path = await Experiment.qc.aom.save_qudi()
        return hdf5_location

    @staticmethod
    def load(path):
        # retrieve the data from HDF5 - ensuring we know we actually have it stored!
        return PsatData.load(Experiment.tables_context, path)



class RabiExperiment:

    def __init__(self, tau_start=0, tau_step=1, tau_points=100, measurement_time=300):
        self.tau_start = tau_start
        self.tau_step = tau_step
        self.tau_points = tau_points
        self.measurement_time = measurement_time

    async def run(self):
        try:
            await self.setup()
            await self.measure()
            Experiment.track.progress("Starting rabi")
            await self.save()
            await self.retrieve_cooked()
            self.fit()
            self.display()
            if not self.fitted:
                raise AbortExperiment("Rabi could not be fitted")
        except CancelledError:
            Experiment.track.progress("Cancelling in pulsed experiment <rabi>")
            self.stop()
            raise CancelledError

    async def setup(self):
        Experiment.qc.pulsed.setup

    def display(self):
        if self.fitted:
            # overlay fit
            pass


class Pulsed:

    def __init__(self, **kwargs):
        self.kwargs = kwargs

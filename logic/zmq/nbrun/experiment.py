from .track import Track
from .wait import InterruptableWaitManager
from asyncio import CancelledError
from logic.zmq.client import *
from .. data.tables_context import TablesContext
from .. data.psat import Psat
from .. data.hbt import Hbt
from .. data.optimizer import OptimizerTrack, OptimizerImage
from .. client.optimizer import RefocusFailed, ZRefocusFailed
from ipywidgets import Output
from IPython.display import display
import numpy as np
import matplotlib.pyplot as plt

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
    wait: InterruptableWaitManager = None
    qc: QudiControl = None
    tables_context: TablesContext = None

    @classmethod
    async def setup(cls, name='anon_experiment', hdf5_file=None, poi_name=None):
        cls.run_name = "{}_{}".format(name, poi_name)
        stop_file = cls.run_name + ".stop"
        cls.track = Track.setup()
        cls.wait = InterruptableWaitManager(stop_file=stop_file, tracker=cls.track)
        cls.qc = QudiControl(session=name, log_suffix=poi_name)
        if hdf5_file:
            await cls.qc.manager.attach_data_file(hdf5_file)
            cls.tables_context = TablesContext(hdf5_file)
        else:
            cls.qc.log.warning(".No HDF5 file attached: you should probably set hdf5_file if storing data")


class Refocus:

    async def refocus(self, poi=None, settings=None, min_count_threshold=None):
        min_count_threshold = min_count_threshold if min_count_threshold is not None else self.min_count_threshold
        if settings is not None:
            # e.g. to set span of optimizer image appropriately
            Experiment.qc.optimizer.setup(settings)
        refocus_done = Experiment.qc.optimizer.pending_refocus()
        await Experiment.qc.optimizer.refocus(poi=poi)
        try:
            x, y, z = await self._result(refocus_done, min_count_threshold)
            await self.save()
            return x, y, z
        except CancelledError:
            await Experiment.qc.optimizer.stop()

    @classmethod
    async def _result(cls, refocus_done, min_count_threshold):
        refocus_result = await refocus_done
        xy_fitted = refocus_result.get('xy_fitted', False)
        z_fitted = refocus_result.get('z_fitted', False)
        if xy_fitted and z_fitted:
            # add heuristics
            # are the max counts reasonable
            try:
                if refocus_result['fitted_z_counts'] < min_count_threshold:
                    raise RefocusWentDark
                if not refocus_result['in_bounds']:
                    return False
            except KeyError:
                pass

            return refocus_result['x'], refocus_result['y'], refocus_result['z']
        else:
            if xy_fitted:
                raise ZRefocusFailed
            else:
                raise RefocusFailed

    @classmethod
    async def save(cls):
        await Experiment.qc.optimizer.save_hdf5()

    # make an instance to hold an output
    def __init__(self, min_count_threshold=np.inf):
        self.min_count_threshold = min_count_threshold
        self.display_out = Output()


    def _update_display(self, image_path:str):
        optimizer_data = OptimizerImage.load(Experiment.tables_context, image_path)


    def display_latest(self):
        display(self.display_out)


class PsatExperiment:

    def __init__(self):
        self.hdf5_path = None
        self.qudi_path = None

    @staticmethod
    async def run(self):
        done = Experiment.qc.aom.pending_psat_done()
        fitted = Experiment.qc.aom.pending_psat_fit()
        await Experiment.qc.aom.take_psat()
        await done
        fit = await fitted
        await self.save()

    async def save(self):
        # ask the Qudi end to save the data
        saved = Experiment.qc.aom.pending_psat_saved()
        self.hdf5_path = await Experiment.qc.aom.save_hdf5()
        self.qudi_path = await Experiment.qc.aom.save_qudi()
        await saved

    def load(self):
        # retrieve the data from HDF5 - ensuring we know we actually have it stored!
        return Psat.load(self.hdf5_path)


class HbtExperiment:

    def __init__(self):
        self.hdf5_path = None
        self.qudi_path = None

    @staticmethod
    async def run(self, time=300):
        done = Experiment.qc.hbt.pending_done()
        await Experiment.qc.hbt.start_timed(time=time)
        await done
        await self.save()

    async def save(self):
        # ask the Qudi end to save the data
        saved = Experiment.qc.hbt.pending_hbt_saved()
        self.hdf5_path = await Experiment.qc.hbt.save_hdf5()
        self.qudi_path = await Experiment.qc.hbt.save_qudi()
        await saved

    def load(self):
        # retrieve the data from HDF5 - ensuring we know we actually have it stored!
        return Hbt.load(self.hdf5_path)



class RabiExperiment:

    def __init__(self, tau_start=0, tau_step=1, tau_points=100, measurement_time=300):
        self.tau_sta.rt = tau_start
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

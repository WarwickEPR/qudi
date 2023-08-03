from .track import Track
from .wait import InterruptableWaitManager
from asyncio import CancelledError
from logic.zmq.client.QudiControl import *
from .. data.tables_context import TablesContext
from .. data.psat import Psat
from .. data.hbt import Hbt

# wrap up all the setup conveniently


class AbortExperiment(Exception):
    def __init__(self, msg=''):
        self.msg = msg

    def __repr(self):
        if self.msg:
            return "Experiment abort: {}".format(self.msg)
        else:
            return "Experiment abort"

# Effectively a singleton for each sub notebook kernel, just for convenience of bundling up setup


class Experiment:

    run_name = ''
    track: Track = None
    wait: InterruptableWaitManager = None
    qc: QudiControl = None
    tables_context: TablesContext = None

    @classmethod
    def setup(cls, name='anon_experiment', hdf5_file=None, poi_name=None):
        cls.run_name = "{}_{}".format(name, poi_name)
        stop_file = cls.run_name + ".stop"
        cls.track = Track.setup()
        cls.wait = InterruptableWaitManager(stop_file=stop_file, tracker=cls.track)
        cls.qc = QudiControl(session=name, log_suffix=poi_name)
        cls.tables_context = TablesContext(hdf5_file)


class Refocus:

    def __init__(self):
        self.hdf5_path = None

    @staticmethod
    async def refocus(self, poi=None, settings=None):
        if settings is not None:
            Experiment.qc.optimizer.setup(settings)
        refocus_done = Experiment.qc.optimizer.pending_refocus()
        await Experiment.qc.optimizer.start_refocus(poi=poi)
        await refocus_done
        await self.save()

    async def save(self):
        await Experiment.qc.optimizer.save_hdf5()

    def display(self):
        pass

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

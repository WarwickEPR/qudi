from . base import ZmqProxy
from core.connector import Connector
from .. message import Message
from contextlib import contextmanager
import tables


class OdmrProxy(ZmqProxy):

    frontend = Connector(interface='ZmqFrontend')
    storage = Connector(interface='TablesStorage')
    odmr = Connector(interface='ODMRLogic')
    confocal = Connector(interface='ConfocalLogic', optional=True)
    poimanager = Connector(interface='PoiManagerLogic')
    aom = Connector(interface='AomLogic')


    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)
        self._start_timestamp = None
        self._hdf_file = None
        self._hdf_path = None
        self._disable_hdf_updates = False

    def on_activate(self):
        super().on_activate()
        self.odmr().module_state.sigStateChanged.connect(self._notify_state_change)

    def on_deactivate(self):
        super().on_deactivate()
        self.odmr().module_state.sigStateChanged.disconnect(self._notify_state_change)

    def _notify_state_change(self, e):
        self.notify('state_change')

    def _notify_scan_stopped(self):
        self.notify('stopped')

    def _notify_scan_started(self):
        self.notify('started', body={'file': self._hdf_file,
                                     'timestamp': self._start_timestamp,
                                     'dataset': self._hdf_path})

    def handle_start_scan(self, msg: Message):
        if self.odmr().module_state.current != 'idle':
            # scanner is currently busy
            self.reply(msg, body='Scanner busy')
            return

        self._setup_odmr(msg)
        self._start_scan()
        self.reply(msg, body='Started')

    def handle_stop_scan(self, msg: Message):
        self.odmr().stop_odmr_scan()
        self.reply(msg, body='Stopped')

    def _setup_odmr(self, msg: Message):

        if not msg.body: return
        if 'clock' in msg.body: self.odmr().set_clock_frequency(msg.body['clock'])
        if 'oversampling' in msg.body: self.odmr().oversampling(msg.body['oversampling'])
        if 'runtime' in msg.body: self.odmr().set_runtime(msg.body['runtime'])
        if 'sweep' in msg.body:
            starts = msg.body['sweep']['starts']  # Hz[]
            stops = msg.body['sweep']['stops']    # Hz[]
            steps = msg.body['sweep']['steps']    # Hz[]
            power = msg.body['sweep']['power']    # dBm
            self.odmr().set_sweep_parameters(starts, stops, steps, power)

    def _start_scan(self, orientation):
        self.odmr().start_odmr_scan()

    def _save_hdf(self):
        poi = self.poimanager().active_poi
        with self.storage().session_file() as h:
            folder, dataset_name = self.storage().dataset_path('ODMR', site=poi)
            for nch, channel in enumerate(self.odmr().get_odmr_channels()):
                # save raw data for each channel
                data: tables.Array = h.create_array(folder,
                                                    "{}_{}".format(channel, dataset_name),
                                                    createparents=True,
                                                    obj=self.odmr().odmr_raw_data[:self.odmr().elapsed_sweeps, nch, :])
                data.attrs['microwave_cw_power_dBm'] = self.odmr().cw_mw_power
                data.attrs['microwave_sweep_power_dBm'] = self.odmr().sweep_mw_power
                data.attrs['run_time'] = self.odmr().run_time
                data.attrs['elapsed_sweeps'] = self.odmr().elapsed_sweeps
                data.attrs['start_frequencies'] = self.odmr().mw_starts
                data.attrs['stop_frequencies'] = self.odmr().mw_stops
                data.attrs['step_sizes'] = self.mw_steps
                data.attrs['clock_frequencies'] = self.clock_frequency
                data.attrs['channel'] = '{0}: {1}'.format(nch, channel)
                data.attrs['poi'] = poi
                data.attrs['roi'] = self.poimanager().roi_name
                data.attrs['position'] = self.poimanager().scanner_position()
                if self.aom():
                    data.attrs['laser_power'] = self.aom().get_power()
                data.flush()

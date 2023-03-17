from . base import ZmqProxy
from core.module import ModuleStateMachine
from core.connector import Connector
from .. message import Message
import tables
from qtpy import QtCore


class OdmrProxy(ZmqProxy):

    frontend = Connector(interface='ZmqFrontend')
    storage = Connector(interface='TablesStorage')
    odmr = Connector(interface='ODMRLogic')
    confocal = Connector(interface='ConfocalLogic', optional=True)
    poimanager = Connector(interface='PoiManagerLogic')
    aom = Connector(interface='AomLogic')

    # mirroring Gui invocation
    sigStartScan = QtCore.Signal()
    sigStopScan = QtCore.Signal()
    sigContinueScan = QtCore.Signal()
    sigFit = QtCore.Signal(str, object, object, int, int)
    sigSave = QtCore.Signal(str, list, list)
    sigMwSweepParamsChanged = QtCore.Signal(list, list, list, float)

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)
        self._start_timestamp = None
        self._hdf_file = None
        self._hdf_path = None
        self._disable_hdf_updates = False

    def on_activate(self):
        super().on_activate()
        self.odmr().module_state.sigStateChanged.connect(self._notify_state_change)
        self.odmr().sigOdmrFitUpdated.connect(self._notify_fit_updated)

        # Additional signals to queue work on the ODMR logic thread
        self.sigStartScan.connect(self.odmr().start_odmr_scan, QtCore.Qt.QueuedConnection)
        self.sigStopScan.connect(self.odmr().stop_odmr_scan, QtCore.Qt.QueuedConnection)
        self.sigContinueScan.connect(self.odmr().continue_odmr_scan, QtCore.Qt.QueuedConnection)
        self.sigFit.connect(self.odmr().do_fit, QtCore.Qt.QueuedConnection)
        self.sigSave.connect(self.odmr().save_odmr_data, QtCore.Qt.QueuedConnection)
        self.sigMwSweepParamsChanged.connect(self.odmr().set_sweep_parameters, QtCore.Qt.QueuedConnection)

    def on_deactivate(self):
        super().on_deactivate()
        self.odmr().module_state.sigStateChanged.disconnect(self._notify_state_change)
        self.sigStartScan.disconnect()
        self.sigStopScan.disconnect()
        self.sigContinueScan.disconnect()
        self.sigFit.disconnect()
        self.sigSave.disconnect()
        self.sigMwSweepParamsChanged.disconnect()

    def _check_idle(self):
        if self.odmr().module_state.current != 'idle':
            # scanner is currently busy
            self.log.warning("ODMR scanner already busy")
            return False
        else:
            return True

    @staticmethod
    def _state_transition_gist(transition: ModuleStateMachine):
        return {'event': transition.event,
                'src': transition.src,
                'dst': transition.dst}

    def _notify_state_change(self, e):
        self.notify(topic='state_change', body=self._state_transition_gist(e))
        if e.event == 'lock':
            self._notify_scan_start()
        elif e.event == 'unlock':
            self._notify_scan_stop()

    def _notify_scan_stop(self):
        self.notify(topic='stop')

    def _notify_scan_start(self):
        self.notify('start', body={'file': self._hdf_file,
                                   'timestamp': self._start_timestamp,
                                   'dataset': self._hdf_path})

    def _notify_fit_updated(self, x, y, fit_result, fit):
        self.notify('fit_updated', body={'x': x, 'y': y, 'fit_result': fit_result, 'fit': fit})

    def handle_start_scan(self, msg: Message):
        if not self._check_idle():
            self.reply(msg, body='Scanner busy')
        else:
            self._setup_odmr(msg)
            self.log.debug("ODMR starting with params: {}".format(msg.body))
            self._start_scan()
            self.reply(msg, body='OK')

    def handle_fit(self, msg: Message):
        fit_function = msg.body.get('fit_function', None)
        channel_index = msg.body.get('channel_index', 0)
        fit_range = msg.body.get('fit_range', 0)
        self.log.debug("Fitting: {} {} {}".format(fit_function, channel_index, fit_range))
        self.sigFit.emit(fit_function, None, None, channel_index, fit_range)

    def handle_fit_functions(self, msg: Message):
        fit_functions = list(self.odmr().fc.fit_list.keys())
        self.reply(msg, body=fit_functions)

    def handle_stop_scan(self, msg: Message):
        self._stop_scan()

    def handle_save_qudi(self, msg: Message):
        tag = msg.body.get('tag', None)
        colorscale_range = msg.body.get('colorscale_range', [0, 1e6])
        percentile_range = msg.body.get('percentile_range', [0, 100])
        self.log.debug("Saving: {} {} {}".format(tag, colorscale_range, percentile_range))
        self.sigSave.emit(tag, colorscale_range, percentile_range)
        # No obvious way to know when this will finish, kick it onto the ODMR thread though

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
            self.sigMwSweepParamsChanged.emit(starts, stops, steps, power)

    def _start_scan(self):
        self.log.debug("Starting ODMR")
        self.sigStartScan.emit()

    def _stop_scan(self):
        self.log.debug("Stopping ODMR")
        self.sigStopScan.emit()

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

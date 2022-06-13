from . base import ZmqProxy, ZmqTimer
from core.connector import Connector
from logic.zmq.message import PubMessage, Message
from .. format.pulsed import PulsedMeasurement
import itertools


class PulsedTimer(ZmqTimer):

    def __init__(self, logic):
        super().__init__()
        self._logic = logic

    @property
    def time_elapsed(self):
        return self._logic.elapsed_time

    def start(self, duration):
        super().start(duration)
        self._logic.start_pulsed_measurement()

    def stop(self):
        super().stop()
        self._logic.stop_pulsed_measurement()


class PulsedProxy(ZmqProxy):

    frontend = Connector(interface='ZmqFrontend')
    storage = Connector(interface='TablesStorage')
    pulsed_measurement = Connector(interface='PulsedMeasurementLogic')
    sequence_generator = Connector(interface='SequenceGeneratorLogic')

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)
        self._timer = None
        self._measurement = None
        self._loaded_predef = None
        self._pending_predef = None

    def on_activate(self):
        # get hold of a handle to optimizer_logic, load if necessary
        # subscribe to key events, emit a message when done
        super().on_activate()
        self._timer = PulsedTimer(self.pulsed_measurement())
        self._timer.update.connect(self.notify_progress)
        self.sequence_generator().sigPredefinedSequenceGenerated.connect(self._sequence_generated)

    def on_deactivate(self):
        super().on_deactivate()
        if self._timer and self._timer.isActive():
            self._timer.stop()
        self.pulsed_measurement().sigMeasurementDataUpdated.disconnect(self.notify_data_updated)

    def handle_start(self, msg: Message):
        timestamp = self.storage().timestamp()
        if 'name' in msg.body:
            name = '{}_{}'.format(msg.body['name'], timestamp)
        else:
            name = timestamp
        if 'duration' in msg.body:
            duration = float(msg.body['duration'])
        else:
            duration = 60

        # with self.storage().tables_context() as h:
        #     self._measurement = PulsedMeasurement.create_group(h, name, self._predefined_parameters())

        # only connect signal when the measurement is started via zmq, otherwise
        # results in errors due to measurement being None if started manually
        # self.pulsed_measurement().sigMeasurementDataUpdated.connect(self._data_updated)

        self._timer.start(duration)

    def handle_stop(self, _):
        # self.pulsed_measurement().sigMeasurementDataUpdated.disconnect(self._data_updated)
        self._timer.stop()

    def handle_pause(self, _):
        # As timer is backed by the pulsed logic module elapsed time, it knows about timer pauses implicitly
        self.pulsed_measurement().pause_pulsed_measurement()

    def handle_continue(self, _):
        self.pulsed_measurement().continue_pulsed_measurement()

    def handle_generate_predefined(self, msg: Message):
        predef_name = msg.body['name']
        predef_parameters = msg.body['parameters']
        self._pending_predef = (predef_name, predef_parameters)
        self.sequence_generator().generate_predefined_sequence(predef_name, predef_parameters)

    def _save_data(self):
        with self.storage().tables_context() as h:
            attrs = self.gather(self.pulsed_measurement(), {'elapsed_sweeps': 'elapsed_sweeps',
                                                            'elapsed_time': 'elapsed_time',
                                                            'alternating': '_alternating',
                                                            'analysis_settings': 'analysis_settings',
                                                            'extraction_settings': 'extraction_settings',
                                                            'number_of_lasers': '_number_of_lasers'})
            self._measurement.save_data(h, self._extracted(), self.logic().laser_data, self.logic().raw_data, attrs)

    def _predefined_parameters(self):
        if self._loaded_predef:
            (predef_name, predef_params) = self._loaded_predef
            return { 'predefined_name': predef_name,
                     'predefined_params': predef_params }
        else:
            return {}

    def _extracted(self):
        x = self.logic().signal_data[0]
        y = self.logic().signal_data[1]
        y_err = self.logic().measurement_error[1]
        alt = self.logic().signal_data[2] if self.logic()._alternating else itertools.repeat(0)
        alt_err = self.logic().measurement_error[2] if self.logic()._alternating else itertools.repeat(0)
        return zip(x, y, y_err, alt, alt_err)

    def _sequence_generated(self, name, success):
        # the first sequence generated event after this module evokes it is expected to be "pending"
        if self._pending_predef:
            if success:
                self._loaded_predef = self._pending_predef
            self._pending_predef = None
        else:
            # if another is loaded by the user after, we don't know about it
            self._loaded_predef = None

        if success:
            self.notify_sequence_generated(name)

    def _data_updated(self):
        self._save_data()
        self.notify_data_updated()

    def notify_data_updated(self):
        self.notify('data', body={'variable': self.pulsed_measurement().signal_data[0], 'signal': self.pulsed_measurement().signal_data[1:], 'error': self.pulsed_measurement().measurement_error[1:]})

    def notify_sequence_generated(self, name):
        self.notify('sequence_generated', name)

    def notify_progress(self):
        self.notify('progress')

    def handle_save_qudi(self, _):
        self.pulsed_measurement().save_measurement_data()

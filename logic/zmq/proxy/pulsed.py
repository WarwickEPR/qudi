from . base import ZmqProxy
from core.connector import Connector
from logic.zmq.message import PubMessage, Message


class PulsedProxy(ZmqProxy):

    frontend = Connector(interface='ZmqFrontend')
    pulsed_measurement = Connector(interface='PulsedMeasurementLogic')
    sequence_generator = Connector(interface='SequenceGeneratorLogic')

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)

    def on_activate(self):
        # get hold of a handle to optimizer_logic, load if necessary
        # subscribe to key events, emit a message when done
        super().on_activate()
        self.pulsed_measurement().sigMeasurementDataUpdated.connect(self.notify_data_updated)
        self.sequence_generator().sigPredefinedSequenceGenerated.connect(self.notify_sequence_generated)

    def on_deactivate(self):
        super().on_deactivate()
        self.pulsed_measurement().sigMeasurementDataUpdated.disconnect(self.notify_data_updated)

    def handle_start(self, _):
        self.pulsed_measurement().start_pulsed_measurement()

    def handle_stop(self, _):
        self.pulsed_measurement().stop_pulsed_measurement()

    def handle_pause(self, _):
        self.pulsed_measurement().pause_pulsed_measurement()

    def handle_continue(self, _):
        self.pulsed_measurement().continue_pulsed_measurement()

    def handle_generate_predefined(self, msg: Message):
        self.sequence_generator().generate_predefined_sequence(msg.body['name'], msg.body['parameters'])

    def notify_data_updated(self):
        self.notify('data', body={'variable': self.pulsed_measurement().signal_data[0], 'signal': self.pulsed_measurement().signal_data[1:], 'error': self.pulsed_measurement().measurement_error[1:]})

    def notify_sequence_generated(self, name, success):
        self.notify('sequence_generated', name)

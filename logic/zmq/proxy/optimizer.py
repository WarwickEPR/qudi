from logic.zmq.handler import MessageHandlerBase
from core.connector import Connector
from logic.optimizer_logic import OptimizerLogic
import zmq


class OptimizerProxy(MessageHandlerBase):

    optimizer = Connector(interface=OptimizerLogic)

    def __init__(self, zmq_sock: zmq.Socket):
        self.super().__init__(zmq_sock)
        # get hold of a handle to optimizer_logic, load if necessary
        # subscribe to key events, emit a message when done
        self.optimizer.sigRefocusFinished.connect()

    def handle_refocus(self, msg: dict):
        # call optimizer to start refocus
        self.optimizer.start_refocus(initial_pos=msg.get('poi'), caller="zmq")
        pass

    def emit_refocused(self, caller_tag, position):
        self.emit([b"refocused", position])


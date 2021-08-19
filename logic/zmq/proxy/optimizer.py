from . base import ZmqProxy
from core.connector import Connector
from logic.optimizer_logic import OptimizerLogic
from logic.zmq.message import PubMessage


class OptimizerProxy(ZmqProxy):

    frontend = Connector(interface='ZmqFrontend')
    optimizer = Connector(interface='OptimizerLogic')

    data_fields = {'xy_data': 'refocus_image',
                   'z_data': 'refocus_z_line',
                   'z_fit_line': 'z_fit_data',
                   'status_vars': '_statusVariables',
                   'xy_size': 'refocus_XY_size',
                   'xy_res': 'optimizer_XY_res',
                   'z_size': 'refocus_Z_size',
                   'z_res': 'optimizer_Z_res',
                   'x': 'optim_pos_x',
                   'x_sigma': 'optim_sigma_x',
                   'y': 'optim_pos_y',
                   'y_sigma': 'optim_sigma_y',
                   'z': 'optim_pos_z',
                   'z_sigma': 'optim_sigma_z'}

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)

    def on_activate(self):
        # get hold of a handle to optimizer_logic, load if necessary
        # subscribe to key events, emit a message when done
        super().on_activate()
        self.optimizer().sigRefocusFinished.connect(self.emit_refocused)

    def on_deactivate(self):
        self.optimizer().sigRefocusFinished.disconnect(self.emit_refocused)
        super().on_deactivate()

    def handle_refocus(self, msg={}):
        # call optimizer to start refocus
        self.optimizer().start_refocus(initial_pos=msg.get('poi'), caller_tag="zmq")

    def handle_setup(self, params):
        self.optimizer().set_refocus_XY_size(params['xy_res'])
        self.optimizer().set_refocus_Z_size(params['z_res'])

    def handle_push_data(self):
        self.emit_data()

    def emit_data(self):
        data = {}
        for a, b in self.data_fields.items():
            try:
                v = getattr(self.optimizer(), b)
                data[a] = v
            except AttributeError as e:
                pass
        self.notify(PubMessage(topic='optimizer.data', body=data))

    def emit_refocused(self, caller_tag, position):
        self.notify(PubMessage(topic='optimizer.refocused', body=position))
        self.emit_data()

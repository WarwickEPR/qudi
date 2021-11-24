from . base import ZmqProxy
from core.connector import Connector
from logic.zmq.message import PubMessage, Message


class OptimizerProxy(ZmqProxy):

    frontend = Connector(interface='ZmqFrontend')
    storage = Connector(interface='HdfStorage')
    optimizer = Connector(interface='OptimizerLogic')
    scanner = Connector(interface='ConfocalLogic')

    attributes = {'status_vars': '_statusVariables',
                  'xy_size': 'refocus_XY_size',
                  'xy_res': 'optimizer_XY_res',
                  'z_size': 'refocus_Z_size',
                  'z_res': 'optimizer_Z_res'}

    data_fields = {'xy_counts': 'xy_refocus_image',
                   'z_counts': 'z_refocus_line',
                   'z_position': '_zimage_Z_values',
                   'z_fit_position': '_fit_zimage_Z_values',
                   'z_fit': 'z_fit_data',
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

    def handle_refocus(self, msg: Message):
        # call optimizer to start refocus
        self.log.debug("Starting refocus")
        if 'poi' in msg.body:
            self.optimizer().start_refocus(caller_tag="zmq")
        else:
            self.optimizer().start_refocus(caller_tag="zmq")

    def handle_setup(self, msg: Message):
        self.optimizer().set_refocus_XY_size(msg.body['xy_res'])
        self.optimizer().set_refocus_Z_size(msg.body['z_res'])

    def handle_save_data(self, _):
        self.emit_data()

    def save_data(self):
        data = {}
        for a, b in self.data_fields.items():
            try:
                v = getattr(self.optimizer(), b)
                data[a] = v
            except AttributeError as e:
                pass

        with self.storage().measurement_folder('optimizer') as f:
            # TODO: change to save as datasets and attributes
            f[''] = data

    def handle_goto_current(self, _):
        x = self.optimizer().optim_pos_x
        y = self.optimizer().optim_pos_y
        z = self.optimizer().optim_pos_z

        self.scanner().set_position('zmq', x=x, y=y, z=z)

    def emit_data(self):
        data_key = self.save_data()
        self.notify(topic='data', body=data_key)

    def emit_refocused(self, caller_tag, position):
        self.notify(topic='refocused', body=position)
        self.emit_data()

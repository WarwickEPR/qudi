import zmq
import asyncio
import zmq.asyncio
from logic.zmq.message import Message, PubMessage
import logging
import time
import h5py

from IPython.display import display
import ipywidgets as widgets


class Subscription:

    def __init__(self, ctx: zmq.Context, publisher, topics=[]):
        self.log = logging.getLogger('broadcast.notifications')
        self.socket = ctx.socket(zmq.SUB)
        try:
            self.socket.connect(publisher)
            if not topics:
                self.log.debug("Subscribing to all")
                self.socket.subscribe('')
            else:
                for topic in topics:
                    self.log.debug("Subscribing to {}".format(topic))
                    self.socket.subscribe(topic)
        except zmq.ZMQError as e:
            self.log.error("Failed to subscribe to {}: {}".format(topics, e))

    def __del__(self):
        # wait half a sec for any operations to finish
        self.socket.close(linger=500)

    async def receive(self):
        topic, body = await self.socket.recv_multipart()
        return PubMessage(frames=(topic, body))


# holder for a running background Task and an associated cancellation button

class BgTask:

    log = logging.getLogger('core.bg')

    def __init__(self, coroutine, on_done=None):
        self.log.debug("Scheduling coroutine {} as task".format(coroutine))
        self.task = asyncio.create_task(coroutine)
        if on_done is not None:
            self.task.add_done_callback(on_done)
        self.cancel_button = widgets.Button(description='',
                                            disabled=False,
                                            button_style='',
                                            tooltip='Stop',
                                            icon='window-close')
        self.cancel_button.style.button_color = 'transparent'

        def cancel(btn):
            self.task.cancel()
            self.cancel_button.disabled = True

        self.cancel_button.on_click(cancel)

    def add_cancel_button(self, out):
        return widgets.HBox(children=[out, self.cancel_button],
                            layout=widgets.Layout(display='flex', justify_content='space-between'))


# The interface for users to use

class QudiControl:

    channel_client = {}
    log = logging.getLogger('core.qudicontrol')

    def __init__(self, data_store=None, do_not_store=False, hostname='127.0.0.1', control_port=7081, pub_port=7082):

        # create an asyncio based ZMQ context
        # this will use the existing event loop
        self.ctx = zmq.asyncio.Context()
        self.storage = None

        # open an HDF storage file (unless explicitly asked not to)
        self.session_name = 'session-' + time.strftime("%Y%m%d-%H%M%S")
        if not do_not_store:
            if data_store:
                filename = data_store
            else:
                filename = self.session_name + '.hdf5'
            try:
                self.storage = h5py.File(filename, 'a', swmr_mode=True)
                # open in SWMR mode to allow readers at same time as writing consistently
                # allowing online processing of results from file
            except Exception as e:
                # Mapped from underlying HDFS but not documented
                self.log.error("Exception opening HDF file: {}".format(e))
                raise e

        # remember where we're connecting to but only make connections when requested
        self.host = hostname
        self.control_port = control_port
        self.pub_port = pub_port
        self.control_uri = 'tcp://{}:{}'.format(hostname, control_port)
        self.pub_uri = 'tcp://{}:{}'.format(hostname, pub_port)
        self.control = self.connect('control')

    @classmethod
    def register(cls, name, client):
        if name:
            cls.log.debug("Registering {} as {}".format(client, name))
            cls.channel_client[name] = client

    # connect to the control port
    # message exchanges are asynchronous and initiated from this end
    # so e.g. a command that doesn't expect a reply, a request which expects a reply or a
    # a series of updates ending in a done message.
    def connect(self, channel):
        control = self.ctx.socket(zmq.DEALER)
        control.connect(self.control_uri)
        if channel in self.channel_client:
            return self.channel_client[channel](self.ctx, self.pub_uri, channel, control)
        else:
            return QudiClient(self.ctx, self.pub_uri, channel, control)

    async def start_logic_modules(self, modules):
        start_commands = map(self.control.start_logic_module, modules)
        await asyncio.gather(*start_commands)

    # convenience method
    def display_all_notifications(self):
        s = self.control.subscribe_all()
        return self.control.display_notifications(s)


class Plugin(type):
    def __new__(mcs, name, bases, class_dict):
        cls = type.__new__(mcs, name, bases, class_dict)
        QudiControl.register(cls.name, cls)
        return cls


# Each notebook makes one of these for each channel they use.
# All share a notebook level ZMQ context
class QudiClient(metaclass=Plugin):

    name = ""
    tasks = []
    log = logging.getLogger('core.qudiclient')

    def __init__(self, ctx, pub_uri, channel, control_socket):
        self.ctx = ctx
        self.channel = channel
        self.pub_uri = pub_uri
        self.control_socket = control_socket
        self.notifier_socket = None
        self.output_task = None
        self.log = logging.getLogger('client.' + str(self.__class__.__name__))

    def subscribe(self, topics=None):
        if not topics:
            topics = [self.channel]
        elif isinstance(topics, str):
            topics = [topics]
        return Subscription(self.ctx, self.pub_uri, topics)

    def subscribe_all(self):
        return Subscription(self.ctx, self.pub_uri, None)

    async def send_command(self, instruction, body=None):
        m = Message(channel=self.channel, f=instruction, body=body)
        self.log.debug("Sending: {}".format(m))
        await self.control_socket.send_multipart(m.frames_to_qudi())

    async def send_control_command(self, instruction, body=None):
        m = Message(channel='control', f=instruction, body=body)
        await self.control_socket.send_multipart(m.frames_to_qudi())

    @staticmethod
    async def _output_notifications(subscription, out):
        while True:
            message = await subscription.receive()
            with out:
                out.append_stdout("Received: {} {}\n".format(message.topic, message.body))

    async def start_logic_module(self, module):
        await self.send_control_command('start_logic_module', module)

    async def receive_message(self):
        reply = await self.control_socket.recv_multipart()
        message = Message.client_from_frontend(frames=reply)
        self.log.debug("Receiving: {}".format(message))
        return message

    async def broadcast(self, message):
        await self.send_command('broadcast', message)

    async def display_notifications(self, subscription):

        out = widgets.Output(layout={'border': '1px solid black'})
        display(out)

        async def output_task(o):
            while True:
                message = await subscription.receive()
                with o:
                    o.append_stdout("Received: {} {}\n".format(message.topic, message.body))
''
        self.output_task = asyncio.create_task(output_task(out))



import zmq
import asyncio
import zmq.asyncio

from logic.zmq.message import Message, PubMessage
import logging

from IPython.display import display
import ipywidgets as widgets


class Subscription:

    def __init__(self, ctx: zmq.Context, publisher, topics=None):
        self.log = logging.getLogger('broadcast.notifications')
        self.socket = ctx.socket(zmq.SUB)
        try:
            self.socket.connect(publisher)
            if not topics:
                self.log.debug("Subscribing to all")
                self.socket.subscribe('')
                return
            elif type(topics) == str:
                self._subscribe(topics)
            else:
                for topic in topics:
                    self._subscribe(topic)

        except zmq.ZMQError as e:
            self.log.error("Failed to subscribe to {}: {}".format(topics, e))

    def _subscribe(self, topic):
        self.log.debug("Subscribing to {}".format(topic))
        self.socket.subscribe(topic)

    def __del__(self):
        # wait half a sec for any operations to finish
        self.socket.close(linger=500)

    async def receive(self):
        topic, body = await self.socket.recv_multipart()
        return PubMessage(frames=(topic, body))


# The interface for users to use
class QudiControl:

    channel_client = {}
    log = logging.getLogger('core.qudicontrol')

    def __init__(self, hostname='127.0.0.1', control_port=7081, pub_port=7082, title=''):
        self.title = title

        # create an asyncio based ZMQ context
        # this will use the existing event loop
        self.ctx = zmq.asyncio.Context()

        # remember where we're connecting to but only make connections when requested
        self.host = hostname
        self.control_port = control_port
        self.pub_port = pub_port
        self.control_uri = 'tcp://{}:{}'.format(hostname, control_port)
        self.pub_uri = 'tcp://{}:{}'.format(hostname, pub_port)
        self.control = self.connect('control')

        # cache for auto-connection of clients
        self._clients = {}

    @classmethod
    def register(cls, name, client):
        if name:
            cls.log.debug("Registering {} as {}".format(client, name))
            cls.channel_client[name] = client

    def __getattr__(self, channel):
        if channel not in self._clients and channel in self.channel_client:
            self._clients[channel] = self.connect(channel)
        if channel in self._clients:
            return self._clients[channel]
        else:
            return AttributeError

    def __dir__(self):
        return list(self.channel_client.keys())

    def client(self, channel):
        if channel not in self._clients:
            self._clients[channel] = self.connect(channel)

        return self._clients[channel]

    # connect to the control port
    # message exchanges are asynchronous and initiated from this end
    # so e.g. a command that doesn't expect a reply, a request which expects a reply or a
    # a series of updates ending in a done message.
    def connect(self, channel):
        control = self.ctx.socket(zmq.DEALER)
        control.connect(self.control_uri)
        if channel in self.channel_client:
            self.log.debug("Channel {} client {}".format(channel, self.channel_client[channel]))
            return self.channel_client[channel](self.ctx, self.pub_uri, channel, control)
        else:
            return QudiClient(self.ctx, self.pub_uri, channel, control)

    # convenience method
    def display_all_notifications(self):
        s = self.control.subscribe_all()
        return self.control.display_notifications(s)

    @classmethod
    def setup_logging(cls, logfile='logs/qc.log'):
        logging.basicConfig(format='%(asctime)s %(name)s:%(levelname)s %(message)s',
                            filename=logfile, encoding='utf-8', filemode='w', level=logging.DEBUG)
        logger = logging.getLogger()
        logger.addFilter(QudiControlLogFilter)


class QudiControlLogFilter(logging.Filter):

    prefix = ['core', 'broadcast', 'client']

    def filter(self, record):
        for p in self.prefix:
            if record.name.startswith(p):
                return True
        return False


class Plugin(type):
    name = ''

    def __new__(mcs, name, bases, class_dict):
        cls = type.__new__(mcs, name, bases, class_dict)
        QudiControl.register(cls.name, cls)
        return cls


# Each notebook makes one of these for each channel they use.
# All share a notebook level ZMQ context
class QudiClient(metaclass=Plugin):

    name = ""
    tasks = []
    log = logging.getLogger('client')

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
        self.log.debug('Sending control command: {}'.format(m))
        await self.control_socket.send_multipart(m.frames_to_qudi())

    async def query(self, instruction, body=None):
        await self.send_command(instruction, body=body)
        reply = await self.receive_message()
        return reply.body

    @staticmethod
    async def _output_notifications(subscription, out):
        while True:
            message = await subscription.receive()
            with out:
                out.append_stdout("Received: {} {}\n".format(message.topic, message.body))

    async def receive_message(self):
        reply = await self.control_socket.recv_multipart()
        message = Message.client_from_frontend(frames=reply)
        self.log.debug("Receiving: {}".format(message))
        return message

    async def broadcast(self, message):
        await self.send_command('broadcast', message)

    async def echo(self, x):
        await self.send_command('echo', body=x)
        reply = await self.receive_message()
        return reply.body

    async def display_notifications(self, subscription):

        out = widgets.Output(layout={'border': '1px solid black'})
        display(out)

        async def output_task(o):
            while True:
                message = await subscription.receive()
                with o:
                    o.append_stdout("Received: {} {}\n".format(message.topic, message.body))

        self.output_task = asyncio.create_task(output_task(out))

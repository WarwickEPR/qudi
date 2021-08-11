import zmq
import asyncio
import zmq.asyncio
from logic.zmq.message import Message, PubMessage
import logging

from IPython.display import display
import ipywidgets as widgets


class Subscription:

    def __init__(self, ctx: zmq.Context, publisher, topics=[]):
        self.log = logging.getLogger('broadcast.notifications')
        self.socket = ctx.socket(zmq.SUB)
        try:
            self.socket.connect(publisher)
            if not topics:
                self.log.info("Subscribing to all")
                self.socket.subscribe('')
                self.socket.setsockopt_string(zmq.SUBSCRIBE, '')
            else:
                for topic in topics:
                    self.log.info("Subscribing to {}".format(topic))
                    self.socket.subscribe(topic)
                    self.socket.setsockopt_string(zmq.SUBSCRIBE, topic)
        except zmq.ZMQError as e:
            self.log.error("Failed to subscribe to {}: {}".format(topics, e))

    def __del__(self):
        # wait half a sec for any operations to finish
        self.socket.close(linger=500)

    async def receive(self):
        topic, contents = await self.socket.recv_multipart()
        return PubMessage(frames=(topic, contents))


# The interface for users to use

class QudiControl:

    channel_client = {}
    log = logging.getLogger('core.qudicontrol')

    def __init__(self, hostname='127.0.0.1', control_port=7081, pub_port=7082):
        # create an asyncio based ZMQ context
        # this will use the existing event loop
        self.ctx = zmq.asyncio.Context()

        # remember where we're connecting to but only make connections when requested
        self.host = hostname
        self.control_port = control_port
        self.pub_port = pub_port
        self.control_uri = 'tcp://{}:{}'.format(hostname, control_port)
        self.pub_uri = 'tcp://{}:{}'.format(hostname, pub_port)

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


class Plugin(type):
    def __new__(mcs, name, bases, class_dict):
        cls = type.__new__(mcs, name, bases, class_dict)
        QudiControl.register(cls.name, cls)
        return cls


# Each notebook makes one of these for each channel they use.
# All share a notebook level ZMQ context
class QudiClient(metaclass=Plugin):

    name = ""

    def __init__(self, ctx, pub_uri, channel, control_socket):
        self.ctx = ctx
        self.channel = channel
        self.pub_uri = pub_uri
        self.control_socket = control_socket
        self.notifier_socket = None
        self.output_task = None

    def subscribe(self, topics=[]):
        if isinstance(topics, str):
            topics = [topics]
        return Subscription(self.ctx, self.pub_uri, topics)

    async def send_command(self, instruction, body):
        m = Message(channel=self.channel, f=instruction, contents=body)
        await self.control_socket.send_multipart(m.encoded_with_envelope())

    async def receive_message(self):
        reply = await self.control_socket.recv_multipart()
        message = Message(frames=reply)
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
                    o.append_stdout("Received: {} {}\n".format(message.topic, message.contents))

        self.output_task = asyncio.create_task(output_task(out))



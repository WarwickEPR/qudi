import zmq
import asyncio
import zmq.asyncio
from logic.zmq.message import Message, PubMessage

from IPython.display import display
import ipywidgets as widgets


# Each notebook makes one of these for each channel they use.
# All share a notebook level ZMQ context
class QudiClient:

    def __init__(self, ctx, pub_uri, channel, control_socket):
        self.ctx = ctx
        self.channel = channel
        self.pub_uri = pub_uri
        self.control_socket = control_socket
        self.notifier_socket = None
        self._subscription = {}

    def subscribe(self, topic):
        self.notifier_socket = self.ctx.socket(zmq.SUB)
        self.notifier_socket.subscribe(topic)
        self.notifier_socket.setsockopt_string(zmq.SUBSCRIBE, topic)
        self.notifier_socket.subscribe(topic)
        self.notifier_socket.setsockopt_string(zmq.SUBSCRIBE, topic)
        self.notifier_socket.connect(self.pub_uri)
        self._subscription[topic] = True

    def unsubscribe(self, topic):
        self.notifier_socket.unsubscribe(topic)
        #self.notifier_socket.setsockopt(zmq.UNSUBSCRIBE, topic)
        self._subscription[topic] = False

    async def send_command(self, instruction, body):
        await self.control_socket.send_multipart(Message(channel=self.channel, f=instruction, contents=body))

    async def receive_message(self):
        reply = await self.control_socket.recv_multipart()
        message = Message(frames=reply)
        return message

    async def receive_notification(self):
        reply = await self.notifier_socket.recv()
        # unpack message
        message = PubMessage(packet=reply)
        return message


class DummyClient(QudiClient):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.output_task = None

    async def echo(self, x):
        await self.send_command('echo', x)
        reply = await self.receive_message()
        message = Message(frames=reply)
        return message.contents

    async def broadcast(self, message):
        await self.send_command('broadcast', message)

    async def output_all_broadcast(self):
        self.subscribe('')

        out = widgets.Output(layout={'border': '1px solid black'})
        out.append_stdout("Starting\n")
        display(out)

        async def output_task(o):
            while True:
                o.append_stdout("\n waiting ...")
                message = await self.receive_notification()
                o.append_stdout(" --- ")
                with o:
                    o.append_stdout("Received: {} {} {}".format(message.topic, message.f, message.contents))

        self.output_task = asyncio.create_task(output_task(out), name='broadcast')


# The interface for users to use

class QudiControl:

    channel_client =\
        {'dummy': DummyClient}

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


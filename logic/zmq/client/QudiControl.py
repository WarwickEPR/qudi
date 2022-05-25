import datetime
import threading
import time

import zmq
import asyncio
import zmq.asyncio

import math

from ipywidgets import Layout

from logic.zmq.message import Message, PubMessage
import logging

from . logging import initialize_logger
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


class BgWait(BgTask):

    def __init__(self, duration, after_wait):
        async def bg_wait():
            await asyncio.sleep(duration)
            if after_wait is not None:
                await after_wait
            self._done = True
        super().__init__(bg_wait())
        self._done = False
        self._duration = duration
        self._start_time = time.time()
        self._progress_task = None
        self._progress_bar = None
        self._update_thread = None

    def time_remaining(self):
        remaining = self._end_time - time.time()
        if remaining < 0:
            remaining = 0
        return remaining

    def time_elapsed(self):
        return time.time() - self._start_time

    @classmethod
    def seconds_to_string(cls, secs):
        return str(datetime.timedelta(seconds=math.floor(secs)))

    def remaining_str(self):
        return '{} remaining of {}'.format(self.seconds_to_string(self.time_remaining()),
                                           self.seconds_to_string(self._duration))

    def update(self):
        self._progress_bar.description = self.remaining_str()
        self._progress_bar.value = self.time_remaining()

    def add_progress_bar(self):

        self._progress_bar = widgets.FloatProgress(value=self.time_remaining(),
                                                   description=self.remaining_str(),
                                                   min=0.0,
                                                   max=self._duration,
                                                   orientation='horizontal',
                                                   bar_style='',
                                                   layout=Layout(width='500px'))

        def bgloop():
            while not self._done:
                self.update()
                time.sleep(0.4)

        self._update_thread = threading.Thread(target=bgloop)
        self._update_thread.start()

        return self._progress_bar


# The interface for users to use

class QudiControl:

    channel_client = {}
    log = logging.getLogger('core.qudicontrol')

    def __init__(self, hostname='127.0.0.1', control_port=7081, pub_port=7082, session=None, log_suffix=None, title=''):

        if session:
            initialize_logger(name=session, suffix=log_suffix)
        else:
            initialize_logger(name='qudi-client', suffix=log_suffix)
        self.session = session
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

    async def init_session(self):
        session_params = await self.data.open_session(name=self.session, title=self.title)
        self.log.info("Session name set to {}. HDFS5 storage at {}".format(session_params['name'], session_params['path']))

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

    async def start_logic_module(self, modules):
        for module in modules:
            await self.send_control_command('start_logic_module', module)

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

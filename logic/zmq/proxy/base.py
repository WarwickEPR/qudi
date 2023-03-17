import zmq
from logic.generic_logic import GenericLogic
from core.connector import Connector
from core.configoption import ConfigOption
from logic.zmq.message import Message, PubMessage
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QEventLoop, QTimer, QObject
from logic.zmq.common import abbreviate_frames
from importlib import reload
import time
import math


class ZmqProxyThread(QThread):

    sigMessageReceived = pyqtSignal(list)

    def __init__(self, proxy):
        super().__init__()
        self._channel = proxy.channel
        self._ctx = proxy.ctx()
        self.proxy = proxy
        self.log = proxy.log
        self.sock = None

    def _send_reply(self, frames):
        self.log.debug("Sending reply: {}".format(abbreviate_frames(frames)))
        self.sock.send_multipart(frames)

    def run(self):

        # open a DEALER socket with channel as identity
        sock = self._ctx.socket(zmq.DEALER)
        sock.setsockopt(zmq.LINGER, ZmqProxy.LINGER_TIME)
        sock.setsockopt_string(zmq.IDENTITY, self._channel)
        sock.connect('inproc://broker')
        self.sock = sock
        frames = Message(channel=self._channel, f='hello').frames_reply_from_backend()
        self.log.debug("Saying hello from {}: {}".format(self._channel, abbreviate_frames(frames)))
        sock.send_multipart(frames)
        self.proxy.sigReply.connect(self._send_reply, Qt.QueuedConnection)

        # say hello to the ROUTER to insert this endpoint in it's routing table
        # future messages from clients will be in a sense 'in reply to this hello'
        # if another module connects as "channel" (or we restart) it will take precedence

        poller = zmq.Poller()
        poller.register(sock, zmq.POLLIN)

        try:
            while not self.isInterruptionRequested():
                # briefly check for waiting ZMQ activity
                active = dict(poller.poll(50))
                #self.log.debug("Polling: {}".format(active))

                # process any sockets needing attention
                if sock in active:
                    # something waiting
                    frames = sock.recv_multipart()
                    self.log.debug('{} proxy received: {}'.format(self._channel, abbreviate_frames(frames)))
                    self.sigMessageReceived.emit(frames)
                # prod Qt to process signals
                self.eventDispatcher().processEvents(QEventLoop.AllEvents)

            self.log.info("{} proxy exiting".format(self._channel))
            poller.unregister(sock)
            sock.close()
        except zmq.ContextTerminated:
            self.log.info("Context terminated, socket closed")


class ZmqTimer(QObject):

    update   = pyqtSignal(int, int)
    done     = pyqtSignal()
    update_period = 1

    def __init__(self):
        super().__init__()
        self._timer = QTimer()
        self.start_time = 0
        self._duration = 0
        self._final_elapsed = 0
        self._timer.timeout.connect(self._tick)
        self._active = False

    def start(self, duration):
        self.start_time = time.time()
        self._duration = duration
        self._active = True
        self._final_elapsed = 0
        self._timer.start(ZmqTimer.update_period * 1000)

    def stop(self):
        self._duration = self.time_elapsed
        self._final_elapsed = self.time_elapsed
        self._active = False
        self._timer.stop()

    @property
    def time_remaining(self):
        remaining = self._duration - self.time_elapsed
        if remaining < 0:
            return 0
        else:
            return remaining

    @property
    def time_elapsed(self):
        return self._final_elapsed if self._final_elapsed else time.time() - self.start_time

    def change_duration(self, duration):
        if self.time_elapsed > duration:
            # already done - stop
            self.stop()
        else:
            self._duration = duration

    def isActive(self):
        return self._active

    #def update(self):
    #    pass

    def _tick(self):
        self.update.emit(self.time_remaining, self.time_elapsed)
        if self.time_remaining == 0 and self._timer.isActive():
            self.stop()
            self.done.emit()


# A base for specific ZMQ-Qt proxies. Threaded Qudi logic layer module that
# connects to other logic modules and handles signalling etc
# Also runs. a Poller to receive and send ZMQ messages

class ZmqProxy(GenericLogic):

    frontend = Connector(interface='ZmqFrontend')
    channel = ConfigOption('channel', '', missing='error')
    sigReply = pyqtSignal(list)
    LINGER_TIME = 0

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)
        self._ctx = None
        self._proxy_thread = None
        self._timers = {}
        self.pub = None

    def on_activate(self):
        # share the server context so we can use inproc://
        # zmq should take care of any synchronisation issues
        self._ctx: zmq.Context = self.frontend().ctx()
        self._proxy_thread = ZmqProxyThread(self)
        self._proxy_thread.start()
        self._proxy_thread.sigMessageReceived.connect(self._handle_frames, Qt.QueuedConnection)

        # open a PUB socket and connect to the XSUB aggregator
        self.pub = self._ctx.socket(zmq.PUB)
        self.pub.setsockopt(zmq.LINGER, ZmqProxy.LINGER_TIME)
        self.pub.connect('inproc://aggregator')

    def on_deactivate(self):
        self._proxy_thread.requestInterruption()
        self._proxy_thread.sigMessageReceived.disconnect(self._handle_frames)
        self._proxy_thread.wait()
        self.pub.close()

    def ctx(self):
        return self._ctx

    def _reply(self, frames):
        self.log.debug("Replying: {}".format(abbreviate_frames(frames)))
        self.sigReply.emit(frames)

    def _handle_frames(self, frames):
        message = Message.backend_from_frontend(frames)
        message.channel = self.channel
        self.log.debug("Handling message: {}".format(message))
        self.handle(message)

    def handle(self, msg: Message):
        # expect router to strip off envelope so we receive:
        # |function|client_envelope|body|
        # message includes an envelope from the client, the channel and the function name
        # as well as any pickle'd body
        # so that is:  |function|client_envelope|body|
        # 3 parts
        # Invoke the relevant handler function if one exists and hand over the message
        # This may/may not result in outgoing replies to 'client_envelope' or notifications
        handler_fn = getattr(self, "handle_" + msg.f, self.handle_unimplemented)
        handler_fn(msg)

    def reply(self, msg: Message, body=None):
        if body is not None:
            msg.body = body
        # sends to the backend router a message:
        # |function|client_envelope|body| which the router receives and prepends with |channel||
        # the application broker then decodes this, extracts client_envelope and sends via the frontend to that client
        # essentially reordering as a 5 part message (with 2 as envelope) as:
        # | client_envelope || channel | function | body |
        # The router strips off the envelope and the client receives: | channel | function | body |
        self._reply(msg.frames_reply_from_backend())

    def reply_ok(self, msg: Message):
        self.reply(msg, body='OK')

    def handle_unimplemented(self, msg: Message):
        self.log.warning("handle_{} not implemented by {}".format(msg.f, type(self)))

    def handle_echo(self, msg: Message):
        self.log.debug("Echoing: {}".format(msg.body))
        self.reply(msg)

    def handle_broadcast(self, msg: Message):
        self.log.debug("Broadcasting: {}".format(msg))
        self.notify(topic=msg.f, body=msg.body)

    def notify(self, topic='', body=''):
        if topic:
            topic = '.'.join([self.channel, topic])
        else:
            topic = self.channel
        notification = PubMessage(topic=topic, body=body)
        self.log.debug("Notification: {}".format(notification))
        self.pub.send_multipart(notification.encoded())

    # gather and remap data from a module
    @staticmethod
    def gather(place, keymap):
        data = {}
        for a, b in keymap.items():
            try:
                v = getattr(place, b)
                data[a] = v
            except AttributeError as e:
                pass

import zmq
from logic.generic_logic import GenericLogic
from core.connector import Connector
from core.configoption import ConfigOption
import importlib
import inspect
from PyQt5 import QtCore
import sys
import logging
import time
from logic.zmq.message import Message, PubMessage

LINGER_TIME = 100


# Base for all message handlers
class MessageHandlerBase:

    # avoid all the complications from the metaclass shenanigans
    # just let the handler declare what it needs and proxy_handler can peek in to ensure they're made available
    # when called.
    # myconn = Connector(interface='Foo')

    # initiated by receiving a message from a remote client
    # hides the message delivery structure from the handler
    # responses are valid as long as the ZMQ context isn't reset
    # (although the other party might go away silently in the meantime)
    def __init__(self, reply_router, channel, message):
        self.reply_router = reply_router
        self.channel = channel
        self.message = message
        self.log = logging.getLogger('logic.zmq.' + channel)
        self.handler = getattr(self, "handle_" + self.message.f, "handle_unimplemented")

    def handle(self):
        # find handler function, if available, and call
        self.handler()

    def handle_unimplemented(self, msg):
        self.log.warning("handle_{} not implemented by {}".format(self.f, type(self)))

    def handle_echo(self):
        self.log.debug("Echoing: {}".format(self.message.contents))
        self.reply(self.create_message())

    def handle_broadcast(self):
        self.log.debug("Broadcasting: {}".format(self.message))
        self.notify(self.create_notification_message())

    def create_message(self, channel=None, f=None, contents=None):
        if channel is None:
            channel = self.channel
        if f is None:
            f = self.message.f
        if contents is None:
            contents = self.message.contents
        return Message(envelope=self.message.envelope, channel=channel, f=f, contents=contents)

    def create_notification_message(self, topic=None, f=None, contents=None):
        if topic is None:
            topic = self.channel
        if f is None:
            f = self.message.f
        if contents is None:
            contents = self.message.contents
        return PubMessage(topic=topic, f=f, contents=contents)

    def reply(self, message: Message):
        if not message.f:
            message.f = self.f
        self.reply_router.reply(message)

    def reply_okay(self, contents=None):
        self.reply(Message(f="OK", contents=contents))

    def reply_failed(self, contents=None):
        self.reply(Message(f="FAIL", contents=contents))

    def notify(self, message: PubMessage):
        if message.topic is None:
            message.topic = self.channel
        self.reply_router.notify(message)


class MessageHandlerLoop(QtCore.QThread):

    def __init__(self, context=None, channel="", handler_class=None):
        super().__init__()
        self.ctx = context
        self.channel = channel
        self.message_handler_type = handler_class
        self.log = logging.getLogger('logic.zmq.loop.' + channel)

        self.control = None
        self.pub = None
        self.poller = None

    def run(self):
        self.control = self.ctx.socket(zmq.PAIR)
        self.control.setsockopt(zmq.LINGER, LINGER_TIME)
        self.control.connect('inproc://handler-{}'.format(self.channel))
        self.pub = self.ctx.socket(zmq.PUB)
        self.pub.setsockopt(zmq.LINGER, LINGER_TIME)
        self.pub.connect('inproc://aggregator')
        self.poller = zmq.Poller()
        self.poller.register(self.control)
        self.control.send_multipart(Message(envelope=b'control', f='started').encoded_with_envelope())

        try:
            # loop doing non-blocking recv and potentially emitting messages via a callback
            while not self.isInterruptionRequested():
                # just block until something comes in
                waiting = dict(self.poller.poll())

                if self.control in waiting:
                    # get message, unpack and dispatch
                    message = Message(frames=self.control.recv_multipart())
                    mh = self.message_handler_type(self, self.channel, message)
                    self.log.debug("Sending message to {}".format(mh))
                    mh.handle()

        except zmq.error.ContextTerminated:
            self.log.debug("ZMQ context terminated")

        except zmq.error.ZMQError as e:
            if e.errno == zmq.ENOTSOCK:
                # poll can throw this during shutdown
                if not self.isInterruptionRequested():
                    self.log.warning("Caught zmq.ENOTSOCK not during shutdown")
                    raise e

        try:
            self.control.send_multipart(Message(envelope=b'control', f='stopped').encoded_with_envelope())
        except zmq.error.ZMQError as e:
            if e.errno == zmq.ENOTSOCK:
                # this can happen if the other end and the context may be going away as well so not
                # really a problem. Would be nice to get the shutdown sequence in order but not essential.
                pass
            else:
                raise e

        self.control.close(linger=1000)
        self.pub.close(linger=1000)

    # reply to client that messaged, must have client envelope
    def reply(self, message: Message):
        self.control.send_multipart(message.encoded_with_envelope())

    # send to all subscribed clients
    def notify(self, message: PubMessage):
        self.pub.send_multipart(message.encoded())


# A threaded Qudi module but just to borrow the configuration and connection behaviour.
# Uses connector(s) to sister to the module(s) it talks to politely, loading it if required
# Subclass and override factory method message_handler to construct
# Start one per channel that acts as a factory for message handlers

class MessageChannel(GenericLogic):
    zmq = Connector(interface='ZMQLogic')
    channel = ConfigOption('channel', '', missing='error')
    handler = ConfigOption('handler', 'logic.zmq.MessageHandlerBase', missing='warn')

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)

        # now config is loaded, look in the message handling class to check what Connector are used.
        # Ensure these are loaded by manager by inserting in the constructor
        # Should behave as if loaded directly here and in the message handler - the __call__ stuff only cares
        # on invocation and this is soon enough for manager to do the connect() stuff
        def is_connector(x):
            return inspect.isclass(x) and issubclass(Connector, x)
        handler_connectors = dict(inspect.getmembers(self.handler, predicate=is_connector))
        self.connectors.update(handler_connectors)
        # doesn't trigger any of the gnarly metaclass multiple inheritance traversal stuff but does that matter?
        self.handler_thread = None
        self.ctx = None

    def on_activate(self):
        # share the server context so we can use inproc://
        # zmq should take care of any synchronisation issues
        self.ctx = self.zmq().ctx()
        self._register_handler()
        _channel = str(self.channel)
        self.handler_thread = MessageHandlerLoop(context=self.ctx,
                                                 channel=_channel,
                                                 handler_class=self.message_handler_type())
        self.handler_thread.start()

    def on_deactivate(self):
        self.handler_thread.requestInterruption()
        time.sleep(1)

    def message_handler_type(self):
        handler = str(self.handler)
        if handler.count('.') < 2:
            # prefix with usual location
            handler = 'logic.zmq.proxy.' + handler

        last_dot = handler.rfind('.')
        module = handler[:last_dot]
        handler_class = handler[last_dot+1:]
        try:
            importlib.import_module(module, handler_class)
            return getattr(sys.modules[__name__], handler_class)
        except AttributeError as e:
            self.log.error("Failed to find ZMQ message handler {} in {}: {}".format(handler_class, module, e))
            raise e
        except ModuleNotFoundError as e:
            self.log.error("Failed to find ZMQ message handling class {} in {}: {}".format(handler_class, module, e))
            raise e

    def _register_handler(self):
        discovery = self.ctx.socket(zmq.PUSH)
        self.log.debug("Registering handler {}".format(self.channel))
        discovery.connect('inproc://discovery')
        self.log.debug("Connected to discovery")
        discovery.send_string(self.channel)
        discovery.close(linger=100)


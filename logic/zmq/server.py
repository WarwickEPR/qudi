from logic.generic_logic import GenericLogic

from PyQt5 import QtCore
import zmq
import time
from core.configoption import ConfigOption
from logic.zmq.message import Message, InvalidMessage
import logging

LINGER_TIME = 100


class ZMQServer(QtCore.QThread):

    # Set up two ZMQ messaging services:
    #   * a set of per-module control channels over DEALER <- (ROUTER : PAIR) -> PAIR
    #     - the DEALER - ROUTER pair is just an asynchronous client - server pattern (as opposed to its synchronous
    #       equivalent REQ - REP which strictly alternates requests and replies). The DEALER ends are in the client.
    #       The ROUTER end is the TCP service exposed by this module. The ROUTER "remembers" connections so it can send
    #       replies back to the client. Messages are passed to and from handler threads over a PAIR-PAIR channel.
    #     - Each client process and each channel makes its own connection via the ROUTER
    #     - Message exchanges start from the client. They may have no direct response or multiple responses or a
    #     conversation over an extended period of time.
    #     - "Connections" are stateless - the messages contain the information required to deliver them
    #     - messages are multi-part, a series of frames that are delivered together
    #     - Whilst each connection is independent, the server context is shared so commands can result in changes which
    #       trigger notifications to any/all other "interested parties" who have subscribed to them

    #   * a notification service shared by all channels which can be filtered by topic/channel
    #     built from PUB <- (XSUB : XPUB) -> SUB
    #     - the (XSUB : PUB) part is just a proxy that allows all publishers and subscribers to contact a
    #       central service, however many are created. If each had their own PUB socket, each would need a TCP port.
    #     - PyZMQ doesn't seem to support multipart PUB-SUB so each message is encoded in one frame
    #
    # Typical use example would be for a client to send a control message over DEALER-ROUTER to initiate a measurement.
    # The client may assumes it's started or wait for confirmation. Then it waits for a notifications over the PUB-SUB
    # channel that the experiment is progressing or has stopped (triggered by Qt signals, timers, whatever).
    # Alternatively the control channel could register/de a handler to emit a message when done. As long as both
    # ends know what to expect either works. The end of the experiment could also be controlled by the client
    # end - e.g. when the uncertainty on a fit has reached a threshold.
    #
    # As there are separate control channels for each handler/module/client process, in the common case where they start
    # something then wait for a subsequent message the channel can just block on waiting for a message. Communication
    # with other modules just continues concurrently and independently. No-one can block the notification channel as it
    # is unidirectional. If you have to wait for a message on a control channel, you can always use non-blocking recv
    # methods, poll for the response or use asyncio.create_task to run a concurrent coroutine but in most cases users
    # can add functionality without getting mired in messy concurrency issues as they're on separate channels and ZMQ
    # deals with delivering inter-thread and inter-process communication safely.
    #
    # Qudi integration
    # ----------------
    # The ZMQLogic module starts a server in a sub-thread. This in turn creates two threads to forward and capture
    # notifications. The server waits to hear from "handlers" over a local socket (simple one way PUSH-PULL).
    # The ZMQProxy module is reused for every handler with a different configuration to plumb in Connectors.
    # Each starts in its own logic thread, with a child handler thread to prevent any block of the Qt event loop.
    # This simply registers the handler with the server, forming a local PAIR-PAIR channel to the handler.
    # The server forwards messages to the appropriate handlers (by prefix) and forwards replies back to the
    # corresponding originator (using the ROUTER attached envelope rather than any state in the component modules).
    #
    # The process is something like a post office that puts letters requesting action into the right pigeon hole and
    # attaches a return slip to let them return correspondence to the originator if the handler has any to send.
    # Handlers use Connectors to load and bind to other modules and messages map to "handle_X" methods to do the work.
    # Requests to connected modules must remember that they come from another, general thread. Not the main GUI
    # thread (where the console runs) or the module thread which has privileged access to state/locked members.
    # This means communication may need to be passed by QueuedConnection signal/slot or synchronised, locked state.
    # Whilst it could be attached with some module extensions, it's easier to manage the potential conflicts between the
    # Qt and networking event loops / blocking operations if we just let them inhabit separate relatively idle threads.

    # ZMQPubProxy starts a proxy in a thread that passes messages between backend publishers and subscribed clients

    class ZMQPubProxy(QtCore.QThread):

        def __init__(self, ctx, bind_address, port, capture=False):
            super().__init__()
            self.ctx = ctx
            self.aggregator = None
            self.pub = None
            self.capture = None
            self.do_capture = capture
            self.bind_address = bind_address
            self.port = port
            self.log = logging.getLogger(__name__ + ".pub")

        def run(self):
            # pass on messages between publishers and subscribers
            self.aggregator = self.ctx.socket(zmq.XSUB)
            self.aggregator.setsockopt(zmq.LINGER, LINGER_TIME)
            self.aggregator.bind('inproc://aggregator')
            self.log.debug('Bound aggregator to {}'.format(self.aggregator))
            # Could put the XPUB end in the client(s) but simpler to let everything subscribe over tcp

            self.pub = self.ctx.socket(zmq.XPUB)
            self.pub.setsockopt(zmq.LINGER, LINGER_TIME)
            pub_address = 'tcp://{}:{}'.format(self.bind_address, self.port)
            self.log.debug('Binding pub socket {} on {}'.format(self.pub, pub_address))
            self.pub.bind(pub_address)

            if self.do_capture:
                self.capture = self.ctx.socket(zmq.PUSH)
                self.capture.setsockopt(zmq.LINGER, LINGER_TIME)
                self.capture.bind('inproc://proxy-capture')

            # proxy will exit as a daemon thread when the context closes
            try:
                if self.do_capture:
                    zmq.proxy(self.pub, self.aggregator, self.capture)
                else:
                    zmq.proxy(self.pub, self.aggregator)
            except zmq.error.ContextTerminated:
                self.log.debug("ZMQ Context terminated. Notification distribution stopped")
            except zmq.error.ZMQError as e:
                if e.errno == zmq.ENOTSOCK:
                    # poll can throw this during shutdown
                    if not self.isInterruptionRequested():
                        self.log.warning("Caught zmq.ENOTSOCK not during shutdown")
                        raise e

            # won't get here, at least until shutdown
            self.pub.close()
            self.aggregator.close()
            if self.capture is not None:
                self.capture.close()

    # ZMQPubCapture starts a thread to capture the proxied frames e.g. for logging
    # If this is

    class ZMQPubCapture(QtCore.QThread):

        def __init__(self, ctx):
            super().__init__()
            self.ctx = ctx
            self.capture = None
            self.log = logging.getLogger(__name__ + ".pub_capture")

        def run(self):
            # pass on messages between publishers and subscribers
            self.capture = self.ctx.socket(zmq.PULL)
            self.capture.setsockopt(zmq.LINGER, LINGER_TIME)
            self.capture.connect('inproc://proxy-capture')
            self.log.debug('Connected proxy capture')

            try:
                while not self.isInterruptionRequested():
                    message = self.capture.recv_multipart()
                    self.log.debug('Forwarding broadcast: {}'.format(message))
            except zmq.error.ContextTerminated:
                self.log.debug("ZMQ Context terminated.")
            except zmq.error.ZMQError as e:
                if e.errno == zmq.ENOTSOCK:
                    # poll can throw this during shutdown
                    if not self.isInterruptionRequested():
                        self.log.warning("Caught zmq.ENOTSOCK not during shutdown")
                        raise e

            # on exit
            self.capture.close()

    def __init__(self,
                 ctx: zmq.Context,
                 bind_address="127.0.0.1",
                 control_port=7081,
                 pub_port=7082,
                 additional_logging=False):
        super().__init__()
        self.ctx = ctx
        self.bind_address = bind_address
        self.control_port = control_port
        self.pub_port = pub_port
        self.more_logging=additional_logging
        self.control_router = None
        self.pub_pump = None
        self.pub_capture = None
        self.discovery = None
        self.poller = None
        self.handler_socket = dict()
        self.handler_started = dict()
        self.log = logging.getLogger(__name__)

    def run(self):
        # external contact point for ZMQ service
        # receiving from remote client, attaches "return to source" envelope
        # sending, this strips the envelope and uses it to return to the correct client
        # received messages are passed to the appropriate handler over a PAIR-PAIR
        self.control_router = self.ctx.socket(zmq.ROUTER)
        self.control_router.setsockopt(zmq.LINGER, LINGER_TIME)
        control_address = 'tcp://{}:{}'.format(self.bind_address, self.control_port)
        self.log.debug('Binding control socket {} on {}'.format(self.control_router, control_address))
        self.control_router.bind(control_address)

        # set up a poller to watch for messages coming in
        self.poller = zmq.Poller()

        # a socket to tell the server that handlers want to connect
        self.discovery = self.ctx.socket(zmq.PULL)
        self.discovery.setsockopt(zmq.LINGER, LINGER_TIME)
        self.discovery.bind('inproc://discovery')
        self.log.debug("Bound discovery internal port: {}".format(self.discovery))
        self.poller.register(self.discovery, zmq.POLLIN)

        # In a background thread, pump messages emitted by PUB via XSUB and out XPUB
        self.pub_pump = self.ZMQPubProxy(self.ctx, self.bind_address, self.pub_port, capture=self.more_logging)
        self.pub_pump.start()

        # Intercept and capture all notifications
        if self.more_logging:
            self.pub_capture = self.ZMQPubCapture(self.ctx)
            self.pub_capture.start()

        # Now enter the polling loop. Pumps messages between sockets
        try:
            while not self.isInterruptionRequested():

                try:
                    # block until something comes in
                    self.log.debug("Waiting for activity on any ZMQ socket")
                    waiting_sockets = self.poller.poll()
                    self.log.debug("Returned from ZMQ poll: {}".format(waiting_sockets))
                    waiting_sockets = dict(waiting_sockets)

                    # first see if any new handlers have been in touch
                    if self.discovery in waiting_sockets:
                        channel = self.discovery.recv_string()
                        self.log.debug("Registering channel {}".format(channel))
                        self._register_handler(channel)

                    # then check for activity from the handlers, have they started up?
                    for handler_name, socket in self.handler_socket.items():
                        self.log.debug("Checking for handler {}".format(handler_name))
                        if socket in waiting_sockets:
                            self.log.debug("Receiving on handler socket")
                            message = socket.recv_multipart()
                            self.log.debug("Received: {}".format(message))
                            m = Message(frames=message)

                            if m.envelope == b'control':

                                if m.f == 'started':
                                    # just started up
                                    self.log.debug("Handler for {} started".format(handler_name))

                                    self.handler_started[handler_name] = True
                                    if all(self.handler_started.values()):
                                        # all handlers register started, open for handling connections from clients
                                        self.log.info("All ZMQ handlers ready, listening for requests")
                                        self._open_for_service()

                                elif m.f == 'stopped':
                                    self.log.debug("Handler for {} stopped, closing socket".format(handler_name))
                                    self.handler_started[handler_name] = False
                                    self.handler_socket[handler_name].close()
                                    self.handler_socket[handler_name].unbind()

                            else:
                                self.log.debug("Sending message out to client via router {}".format(m.str()))
                                # normal messages just to return to peer. Already has the envelope attached so just send!
                                self.control_router.send_multipart(m.encoded_with_envelope())

                    if self.control_router in waiting_sockets:
                        # message has arrived from a client, with return envelope prepended by the router
                        # unpack the message to see where it needs to go to
                        self.log.debug("Control message ready")
                        m = Message(frames=self.control_router.recv_multipart())
                        self.log.debug("Control message: {} {} {} {}".format(m.envelope, m.channel, m.f, m.contents))
                        self.handler_socket[channel].send_multipart(m.encoded_with_envelope())

                except InvalidMessage as e:
                    self.log.warning("Invalid message: {}".format(e.msg))

        except zmq.error.ContextTerminated:
            self.log.debug("ZMQ Context terminated")

        except zmq.error.ZMQError as e:
            if e.errno == zmq.ENOTSOCK:
                # poll can throw this during shutdown
                if not self.isInterruptionRequested():
                    self.log.warning("Caught zmq.ENOTSOCK not during shutdown")
                    raise e

        # Loop has exited due to interruption, interrupt child threads
        self.control_router.close()
        self.discovery.close()
        for s in self.handler_socket.values():
            s.close()
        self.pub_pump.requestInterruption()
        if self.pub_capture is not None:
            self.pub_capture.requestInterruption()

    def _register_handler(self, channel):
        # could use ROUTER-DEALER if multiple handler threads are needed
        # but the work in each handler should be minimal and asynchronous
        # so unless concurrent handling becomes necessary use 1:1 PAIR-PAIR sockets
        handler_socket = self.ctx.socket(zmq.PAIR)
        handler_socket.setsockopt(zmq.LINGER, LINGER_TIME)
        for i in range(1, 5):
            try:
                handler_socket.bind('inproc://handler-{}'.format(channel))
                break
            except zmq.error.ZMQError:
                # probably address in use, try again after a short time
                # just in case the socket is taking time to unbind
                time.sleep(i)
                self.log.debug("Retrying connecting handler {}".format(channel))

        self.poller.register(handler_socket, zmq.POLLIN)
        self.handler_socket[channel] = handler_socket
        self.handler_started[channel] = False

    def _open_for_service(self):
        self.poller.register(self.control_router, zmq.POLLIN)


class ZMQLogic(GenericLogic):

    """Module to expose Qudi functionality for remote control over ZMQ.
    This module holds the ZMQ context and starts the ZMQ control and publishing servers.
    Each message channel (normally communicating with one Qudi module) has a generic proxy module
    running in a separate thread which passes messages to a simple MessageHandler implementation and
    sends out any responses or notifications"""

    bind_address = ConfigOption('bind_address', '127.0.0.1', missing='error')
    control_port = ConfigOption('control_port', 7701, missing='error')
    pub_port = ConfigOption('pub_port', 7702, missing='error')
    more_logging = ConfigOption('more_logging', False)

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)
        self._ctx = None
        self._server = None

    def on_activate(self):
        """ Initialisation performed during activation of the module.

        @return int: error code (0:OK, -1:error)
        """
        self._ctx = zmq.Context()
        self._server = ZMQServer(self._ctx,
                                 bind_address=self.bind_address,
                                 control_port=self.control_port,
                                 pub_port=self.pub_port,
                                 additional_logging=self.more_logging)
        self._server.start()

    def register_handler(self, channel):
        # could do fancy automatic discovery but just tell the server about the channel and let them connect
        self._server.register_handler(channel)

    def ctx(self):
        # reference to the ZeroMQ context. This can be safely shared between threads and allows inproc:// communication
        return self._ctx

    def on_deactivate(self):
        """ Reverse steps of activation

        @return int: error code (0:OK, -1:error)
        """
        # ask threads to exit their loops
        time.sleep(1)  # give other ZMQ modules a little time to start closing up ...
        self._server.requestInterruption()
        time.sleep(1)

        # close sockets and terminate the context
        self._ctx.destroy()

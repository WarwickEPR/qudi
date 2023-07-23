import zmq
from logic.generic_logic import GenericLogic
from core.configoption import ConfigOption
from logic.zmq.message import Message, PubMessage
from threading import Thread
from . message import abbreviate_frames


class ZmqFrontend(GenericLogic):

    LINGER_TIME = 0
    _message_port = ConfigOption('message_port', 7081, missing='warn')
    _notification_port = ConfigOption('notification_port', 7082, missing='warn')
    _log_notifications = ConfigOption('log_notification', False)
    _bind_address = '127.0.0.1'

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)
        self._ctx = None
        self._stop = False

    def ctx(self):
        return self._ctx

    def on_activate(self):
        self._ctx = zmq.Context()
        self._start_notification_proxy()
        self._start_message_broker()
        if self._log_notifications:
            self._start_notification_capture()

        # Also ensure start up the general purpose manager proxy, already done if zmq_manager is loaded first
        self._manager.startModule('logic', 'zmq_manager')

    def on_deactivate(self):
        self.log.info("Terminating ZMQ context")
        self._stop = True
        self._ctx.term()
        # when the context terminates, the proxy will exit. Join the thread
        # use a plain native thread as no Qt communication is needed
        if self._proxy_thread.is_alive():
            self._proxy_thread.join(timeout=5)
        if self._broker_thread.is_alive():
            self._broker_thread.join(timeout=5)

    def _start_notification_proxy(self):
        self.log.info("Starting ZMQ notification proxy")
        self._proxy_thread = Thread(target=self._notification_proxy, daemon=True)
        self._proxy_thread.start()

    # thread that runs a ZMQ proxy forwarding notifications
    def _notification_proxy(self):

        # pass on messages between publishers and subscribers
        xsub = self._ctx.socket(zmq.XSUB)
        xsub.setsockopt(zmq.LINGER, ZmqFrontend.LINGER_TIME)
        self.log.debug("Binding aggregator")
        xsub.bind('inproc://aggregator')

        # outgoing to client and forwarding subscriptions
        xpub = self._ctx.socket(zmq.XPUB)
        xpub.setsockopt(zmq.LINGER, ZmqFrontend.LINGER_TIME)
        pub_address = 'tcp://{}:{}'.format(self._bind_address, self._notification_port)
        xpub.bind(pub_address)

        # proxy will exit as a daemon thread when the context closes
        capture = None
        try:
            if self._log_notifications:
                capture = self._ctx.socket(zmq.PUSH)
                capture.setsockopt(zmq.LINGER, ZmqFrontend.LINGER_TIME)
                capture.bind('inproc://notification-capture')
                zmq.proxy(xpub, xsub, capture)
            else:
                zmq.proxy(xpub, xsub)

        except zmq.error.ContextTerminated:
            self.log.debug("ZMQ Context terminated. Notification distribution stopped")
            xpub.close()
            xsub.close()
            if capture is not None:
                capture.close()

        except zmq.error.ZMQError as exc:
            if exc.errno == zmq.ENOTSOCK:
                # poll can throw this during shutdown
                if not self._ctx.closed:
                    self.log.warning("Notification proxy caught zmq.ENOTSOCK not during shutdown")

    def _start_message_broker(self):
        self.log.info("Starting ZMQ message broker")
        self._broker_thread = Thread(target=self._message_broker, daemon=True)
        self._broker_thread.start()

    def _message_broker(self):

        # bind frontend router
        frontend = self._ctx.socket(zmq.ROUTER)
        frontend.setsockopt(zmq.LINGER, ZmqFrontend.LINGER_TIME)
        frontend_address = 'tcp://{}:{}'.format(self._bind_address, self._message_port)
        self.log.debug("Binding message frontend port")
        frontend.bind(frontend_address)

        # bind backend router
        backend = self._ctx.socket(zmq.ROUTER)
        backend.setsockopt(zmq.LINGER, ZmqFrontend.LINGER_TIME)
        backend_address = 'inproc://broker'
        self.log.debug("Binding message backend port")
        backend.bind(backend_address)

        # routers are back to back, they need some application logic to pass messages between them
        poller = zmq.Poller()
        poller.register(frontend, zmq.POLLIN)
        poller.register(backend, zmq.POLLIN)

        self.log.debug("Frontend: {}".format(frontend))
        self.log.debug("Backend: {}".format(backend))

        try:

            while not self._stop:
                active = dict(poller.poll(50))
                #self.log.debug("Active sockets: {}".data(active))

                if frontend in active:
                    frames = frontend.recv_multipart()
                    msg = Message.frontend_from_client(frames)
                    self.log.debug("Frontend received: {}".format(msg))

                    # special shortcut for "meta" commands
                    if msg.channel == 'control':
                        self.log.debug("Frontend received control message: {}".format(msg))
                        self.control_command(msg)
                    else:
                        backend.send_multipart(msg.frames_to_backend())

                if backend in active:
                    frames = backend.recv_multipart()
                    self.log.debug("Backend received: {}".format(abbreviate_frames(frames)))
                    msg = Message.frontend_from_backend(frames)
                    if msg.channel == 'broker':
                        self.log.debug("Message received for broker: {}".format(msg))
                        # message from backend to us
                        if msg.f == 'hello':
                            # backend just introducing itself to the routing table, job done by socket
                            pass
                    else:
                        frames = msg.frames_reply_to_client()

                        self.log.debug("Replying to client: {}".format(abbreviate_frames(frames)))
                        frontend.send_multipart(frames)

        except zmq.ContextTerminated:
            self.log.info("Broker loop exiting as context terminated")

    def control_command(self, msg):
        # special messages from client
        if msg.f == 'start_logic_module':
            module = msg.body
            self.log.debug("Loading logic module {}".format(module))
            if module in self._manager.tree['defined']['logic'] and not self._manager.isModuleLoaded('logic', module):
                self.log.info("Loading module {}".format(module))
                self._manager.startModule('logic', module)
        else:
            self.log.debug("Unrecognised control message {}({})".format(msg.f, msg.body))

    def _start_notification_capture(self):
        self.log.info("Starting notification capture")
        self._notification_thread = Thread(target=self._notification_capture, daemon=True)
        self._notification_thread.start()

    def _notification_capture(self):
        # capture notifications passing through proxy and log
        capture = self._ctx.socket(zmq.PULL)
        capture.setsockopt(zmq.LINGER, ZmqFrontend.LINGER_TIME)
        capture_address = 'inproc://notification-capture'
        capture.bind(capture_address)
        self.log.info("Notification capture started")

        poller = zmq.Poller()
        poller.register(capture, zmq.POLLIN)

        try:
            while not self._stop:
                active = dict(poller.poll(50))
                if capture in active:
                    frames = capture.recv_multipart()
                    msg = str(PubMessage(frames))[:30]
                    self.log.debug(msg)

        except zmq.ContextTerminated:
            self.log.info("Notification capture loop exiting as context terminated")

        self.log.info("Notification capture loop exiting")
import pickle


def to_bytes(x: str):
    return bytes(x, 'utf-8')


def from_bytes(x: bytes):
    return x.decode('utf-8')


class InvalidMessage(Exception):
    def __init__(self, msg):
        self.msg = msg


class Message:

    def __init__(self, channel='', f='', body=None):
        self._channel = to_bytes(channel)
        self._f = to_bytes(f)
        if body is not None:
            self._body = pickle.dumps(body)
        else:
            self._body = b''
        self._client_envelope = b''

    def __repr__(self):
        if self._client_envelope:
            return "Message({}, {}) client({}) with {} bytes of encoded body".format(self._channel, self._f, self._client_envelope, len(self._body))
        else:
            return "Message({}, {}) with {} bytes of encoded body".format(self._channel, self._f, len(self._body))

    @classmethod
    def _build(cls, channel=b'', f=b'', body=b'', client_envelope=None):
        m = cls()
        m._channel = channel
        m._f = f
        m._body = body
        if client_envelope:
            m._client_envelope = client_envelope
        return m

    @property
    def channel(self):
        return from_bytes(self._channel)

    @channel.setter
    def channel(self, channel: str):
        self._channel = to_bytes(channel)

    @property
    def f(self):
        return from_bytes(self._f)

    @f.setter
    def f(self, f: str):
        self._f = to_bytes(f)

    @property
    def body(self):
        return pickle.loads(self._body)

    @body.setter
    def body(self, body):
        self._body = pickle.dumps(body)

    @classmethod
    def frontend_from_client(cls, frames):
        [client_envelope, channel, f, body] = frames
        return cls._build(channel=channel, f=f, body=body, client_envelope=client_envelope)

    @classmethod
    def backend_from_frontend(cls, frames):
        [client_envelope, f, body] = frames
        return cls._build(client_envelope=client_envelope, f=f, body=body)

    @classmethod
    def frontend_from_backend(cls, frames):
        [_, client_envelope, channel, f, body] = frames
        return cls._build(channel=channel, client_envelope=client_envelope, f=f, body=body)

    @classmethod
    def client_from_frontend(cls, frames):
        [channel, f, body] = frames
        return cls._build(channel=channel, f=f, body=body)

    def frames_to_qudi(self):
        return [self._channel, self._f, self._body]

    def frames_to_backend(self):
        return [self._channel, self._client_envelope, self._f, self._body]

    def frames_reply_from_backend(self):
        return [self._client_envelope, self._channel, self._f, self._body]

    def frames_reply_to_client(self):
        return [self._client_envelope, self._channel, self._f, self._body]


class PubMessage:

    def __init__(self, frames=None, topic="", body=None):
        # PUB/SUB messages are two frames, topic and body

        if frames is not None:
            # from wire
            topic, body = frames
            self.topic = from_bytes(topic)
            if body == '':
                self.body = ''
            else:
                self.body = pickle.loads(body)

        else:
            # from params
            self.topic = topic
            if body is None:
                self.body = ''
            else:
                self.body = body

    def __str__(self):
        return 'PubMessage(topic={}) with {} bytes of contents'.format(self.topic, len(self.body))

    def encoded(self):
        return [to_bytes(self.topic), pickle.dumps(self.body)]

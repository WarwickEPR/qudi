import pickle


def to_bytes(x: str):
    return bytes(x, 'utf-8')


def from_bytes(x: bytes):
    return x.decode('utf-8')


class InvalidMessage(Exception):
    def __init__(self, msg):
        self.msg = msg


class Message:

    SEP = b''

    def __init__(self, frames=None, envelope=None, channel="", f="", contents=None):
        self.envelope = None

        if frames is not None:
            # from the wire
            if len(frames) == 5:
                # envelope provided
                # e.g. from router to handler
                (envelope, _, channel, f, contents) = frames
                self.envelope = envelope
            elif len(frames) == 4:
                # i.e. outbound from router, envelope stripped
                (_, channel, f, contents) = frames
#            elif len(frames) == 3:
#                # no envelope
#                (channel, f, contents) = frames
            else:
                raise InvalidMessage(frames)

            self.channel = from_bytes(channel)
            self.f = from_bytes(f)
            self.contents = pickle.loads(contents)

        else:
            # from parameters
            self.envelope = envelope
            self.channel = channel
            self.f = f
            self.contents = contents

    def __str__(self):
        return 'Message(envelope={}, channel={}, f={}) with {} bytes of contents'\
            .format(self.envelope, self.channel, self.f, len(self.contents))

    def encoded_with_envelope(self):
        if self.envelope is not None:
            return [self.envelope, Message.SEP] + self.encoded()
        else:
            return [Message.SEP] + self.encoded()

    def encoded(self):
        return [to_bytes(self.channel), to_bytes(self.f), pickle.dumps(self.contents)]


class PubMessage:

    def __init__(self, frames=None, topic="", contents=None):
        # PyZMQ doesn't seem to support multipart pub-sub
        # revert to encoding in one message of two frames

        if frames is not None:
            # from wire.
            topic, contents = frames
            self.topic = from_bytes(topic)
            self.contents = pickle.loads(contents)

        else:
            # from params
            self.topic = topic
            self.contents = contents

    def __str__(self):
        return 'PubMessage(topic={}:{}) with {} bytes of contents'.format(self.topic, len(self.contents))

    def encoded(self):
        return [to_bytes(self.topic), pickle.dumps(self.contents)]


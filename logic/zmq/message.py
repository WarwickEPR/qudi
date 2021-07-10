import pickle
import logging


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
                (envelope, _, channel, f, contents) = frames
                self.envelope = envelope
            elif len(frames) == 3:
                # no envelope
                (channel, f, contents) = frames
            else:
                raise InvalidMessage([frames])

            self.channel = from_bytes(channel)
            self.f = from_bytes(f)
            self.contents = pickle.loads(contents)

        else:
            # from parameters
            self.envelope = envelope
            self.channel = channel
            self.f = f
            self.contents = contents

    def encoded_with_envelope(self):
        if self.envelope is not None:
            return [self.envelope, Message.SEP] + self.encoded()
        else:
            return [Message.SEP] + self.encoded()

    def encoded(self):
        return [to_bytes(self.channel), to_bytes(self.f), pickle.dumps(self.contents)]


class PubMessage:

    def __init__(self, packet=None, topic="", f="", contents=None):
        # PyZMQ doesn't seem to support multipart pub-sub
        # revert to encoding in one message

        if packet is not None:
            # from wire.
            header, contents = packet.split(' ', 2)
            topic, f = header.split(':', 2)
            self.topic = from_bytes(topic)
            self.f = from_bytes(f)
            self.contents = pickle.loads(contents)

        else:
            # from params
            self.topic = topic
            self.f = f
            self.contents = contents

    def encoded(self):
        return "%s:%s %s" % (to_bytes(self.topic), to_bytes(self.f), pickle.dumps(self.contents))


"""Synthetic controller replies. This helper never opens a socket."""

import asyncio
import struct


POSE_VALUES = (150.0, 50.0, 100.0, 0.0, 10.0, 20.0, 100.0, -30.0)


def response(command: int, payload: bytes, control: int = 0) -> bytes:
    body = bytes((command, control)) + payload
    return b"\xaa\xaa" + bytes((len(body),)) + body + bytes(((-sum(body)) % 256,))


def pose_reply() -> bytes:
    return response(10, struct.pack("<8f", *POSE_VALUES))


def alarm_reply(nonzero: bool = False) -> bytes:
    data = bytearray(32)
    if nonzero:
        data[8] = 0x25
    return response(20, data)


class FakeTransport:
    def __init__(self, responder=None):
        self.responder = responder
        self.sent = []
        self.incoming = asyncio.Queue()
        self.open = False

    async def connect(self):
        self.open = True
        self.incoming = asyncio.Queue()

    async def send(self, raw):
        if not self.open:
            raise ConnectionError("fake transport closed")
        self.sent.append(raw)
        if self.responder:
            for reply in self.responder(raw):
                self.incoming.put_nowait(reply)

    async def receive(self):
        item = await self.incoming.get()
        if isinstance(item, Exception):
            raise item
        return item

    async def close(self):
        self.open = False


def normal_responder(raw):
    return [pose_reply() if raw[3] == 10 else alarm_reply()]

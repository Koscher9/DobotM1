"""Offline trace transport. No socket or live transport is ever constructed."""

import asyncio
import json
from pathlib import Path

from .protocol import ReadCommand, encode_read


class ReplayMismatch(RuntimeError):
    pass


def load_trace(path: Path) -> list[dict]:
    if path.stat().st_size > 16 * 1024 * 1024:
        raise ValueError("Replay input exceeds the 16 MiB recording limit")
    events = []
    sessions = set()
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        event = json.loads(line)
        if not isinstance(event, dict) or event.get("schema") != 1:
            raise ValueError(f"Unsupported trace schema at line {number}")
        if event.get("event") not in ("tx", "rx", "rx_text"):
            continue
        session_id = event.get("session_id")
        if not isinstance(session_id, str) or not session_id:
            raise ValueError(f"Missing session identity at line {number}")
        sessions.add(session_id)
        if event["event"] == "rx_text":
            if not isinstance(event.get("text"), str) or len(event["text"]) > 65536:
                raise ValueError(f"Invalid text message at line {number}")
        else:
            raw = event.get("raw_hex")
            if not isinstance(raw, str) or len(raw) > 196608:
                raise ValueError(f"Invalid binary message at line {number}")
            data = bytes.fromhex(raw)
            if len(data) > 65536:
                raise ValueError(f"Message too large at line {number}")
            if event["event"] == "tx" and data not in {encode_read(c) for c in ReadCommand}:
                raise ValueError("Replay input contains a non-diagnostic request")
        events.append(event)
    if len(sessions) != 1 or not any(e["event"] == "tx" for e in events):
        raise ValueError("Replay requires one nonempty diagnostic session per file")
    return events


class ReplayTransport:
    def __init__(self, events: list[dict]) -> None:
        self.events = events
        self.sent: list[bytes] = []
        self._index = 0
        self._open = False
        self._incoming: asyncio.Queue = asyncio.Queue()

    async def connect(self) -> None:
        if self._open:
            raise ReplayMismatch("Replay is already open")
        self.sent.clear()
        self._incoming = asyncio.Queue()
        self._index = 0
        self._open = True
        self._pump()

    def _pump(self) -> None:
        while self._index < len(self.events):
            event = self.events[self._index]
            if event["event"] == "tx":
                return
            self._index += 1
            if event["event"] == "rx":
                self._incoming.put_nowait(bytes.fromhex(event["raw_hex"]))
            elif event["event"] == "rx_text":
                self._incoming.put_nowait(event["text"])

    async def send(self, raw: bytes) -> None:
        if not self._open or self._index == len(self.events):
            raise ReplayMismatch("No recorded request remains")
        expected = self.events[self._index]
        if expected["event"] != "tx" or bytes.fromhex(expected["raw_hex"]) != raw:
            raise ReplayMismatch("Requested command differs from the recorded request order")
        self.sent.append(raw)
        self._index += 1
        self._pump()

    async def receive(self) -> bytes | str:
        if not self._open:
            raise ReplayMismatch("Replay is not open")
        return await self._incoming.get()

    async def close(self) -> None:
        self._open = False

    @property
    def complete(self) -> bool:
        return self._index == len(self.events) and self._incoming.empty()

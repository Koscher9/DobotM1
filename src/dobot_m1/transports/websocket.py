"""Explicit WebSocket transport; no reconnect loop and no proxy discovery."""

import asyncio
import math
from urllib.parse import urlsplit


def validate_uri(uri: str) -> None:
    try:
        parts = urlsplit(uri)
        port = parts.port
    except ValueError as exc:
        raise ValueError("Invalid WebSocket URI") from exc
    if parts.scheme not in ("ws", "wss") or not parts.hostname:
        raise ValueError("URI must use ws:// or wss:// and include a host")
    if parts.username or parts.password or parts.fragment or port == 0:
        raise ValueError("Credentials, fragments and port 0 are not supported")


class WebSocketTransport:
    def __init__(self, uri: str, timeout: float = 5.0) -> None:
        validate_uri(uri)
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("Transport timeout must be finite and positive")
        self.uri = uri
        self.timeout = timeout
        self._ws = None

    async def connect(self) -> None:
        if self._ws is not None:
            raise RuntimeError("Transport is already open")
        from websockets.asyncio.client import connect

        self._ws = await connect(
            self.uri, open_timeout=self.timeout, close_timeout=self.timeout,
            ping_interval=None, compression=None, max_size=65536, proxy=None,
        )

    async def send(self, raw: bytes) -> None:
        if self._ws is None:
            raise ConnectionError("Transport is not open")
        await asyncio.wait_for(self._ws.send(raw), self.timeout)

    async def receive(self) -> bytes | str:
        if self._ws is None:
            raise ConnectionError("Transport is not open")
        return await self._ws.recv()

    async def close(self) -> None:
        ws, self._ws = self._ws, None
        if ws is not None:
            await asyncio.wait_for(ws.close(), self.timeout)

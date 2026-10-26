"""Single receiver and serialized verified reads, scoped to one connection."""

import asyncio
import math
import time
import uuid
from typing import Callable

from .diagnostics import TraceRecorder
from .models import Observation, Validity
from .protocol import Frame, FrameDecoder, ReadCommand, decode_read, encode_read
from .transports import Transport


class DiagnosticError(RuntimeError):
    pass


class ReadTimeout(DiagnosticError):
    pass


class ReadOnlySession:
    def __init__(self, transport: Transport, recorder: TraceRecorder | None = None,
                 timeout: float = 1.5, max_age: float = 2.0,
                 clock: Callable[[], float] = time.monotonic) -> None:
        if not all(math.isfinite(v) and v > 0 for v in (timeout, max_age)):
            raise ValueError("Timeout and maximum data age must be finite and positive")
        self.transport, self.recorder = transport, recorder
        self.timeout, self.max_age, self.clock = timeout, max_age, clock
        self.session_id = ""
        self.connected = False
        self._reader: asyncio.Task | None = None
        self._lock = asyncio.Lock()
        self._decoder = FrameDecoder()
        self._pending: tuple[ReadCommand, asyncio.Future] | None = None
        self._pending_version: int | None = None
        self._tainted: set[ReadCommand] = set()
        self._values: dict[ReadCommand, Observation] = {}
        self.last_error: str | None = None

    def _log(self, event: str, **fields) -> None:
        if self.recorder is not None:
            self.recorder.record(event, self.session_id, **fields)

    def observation(self, command: ReadCommand) -> Observation:
        return self._values.get(command, Observation(self.session_id)).evaluated(self.clock(), self.max_age)

    def _invalidate_all(self, error: str) -> None:
        for command in ReadCommand:
            self._values[command] = Observation(self.session_id, Validity.INVALID, error=error)

    async def connect(self) -> None:
        if self.connected or self._reader is not None or self._pending is not None:
            raise DiagnosticError("Close the previous diagnostic session first")
        self.session_id = uuid.uuid4().hex
        self._values.clear()
        self._tainted.clear()
        self._decoder.clear()
        self.last_error = None
        try:
            await self.transport.connect()
            self._log("connected")
        except BaseException:
            await self.transport.close()
            raise
        self.connected = True
        self._reader = asyncio.create_task(self._receive(), name="m1-diagnostic-reader")

    async def close(self) -> None:
        self.connected = False
        self._invalidate_all("connection closed")
        self._fail_pending("connection closed")
        reader, self._reader = self._reader, None
        if reader:
            reader.cancel()
            try:
                await reader
            except asyncio.CancelledError:
                pass
        await self.transport.close()
        # Deliberately no JOG stop or other Dobot write in this read-only mode.
        self._log("disconnected")

    async def read(self, command: ReadCommand, version_index: int | None = None) -> Observation:
        raw = encode_read(command, version_index)
        async with self._lock:
            if not self.connected:
                raise DiagnosticError("No active diagnostic connection")
            if command in self._tainted:
                raise DiagnosticError(f"CMD {command.value} has an ambiguous prior response; reconnect before retrying")
            self._values[command] = Observation(self.session_id)
            future = asyncio.get_running_loop().create_future()
            self._pending = (command, future)
            self._pending_version = version_index
            sent = False
            try:
                self._log("tx", raw_hex=raw.hex(" "), command=command.value, request_id=uuid.uuid4().hex)
                sent = True
                await self.transport.send(raw)
                result = await asyncio.wait_for(future, self.timeout)
                if not self.connected:
                    raise DiagnosticError(self.last_error or "Connection closed before the read completed")
                # Preserve the receiver's timestamp; never revive data invalidated
                # by a later frame error or disconnect while this task was asleep.
                return result
            except asyncio.TimeoutError as exc:
                self._tainted.add(command)
                self._decoder.clear()
                message = f"No valid response to CMD {command.value}; reconnect before repeating this read"
                self._values[command] = Observation(self.session_id, Validity.INVALID, error=message)
                self._log("read_timeout", command=command.value)
                raise ReadTimeout(message) from exc
            except BaseException as exc:
                if sent:
                    self._tainted.add(command)
                    self._decoder.clear()
                self._values[command] = Observation(self.session_id, Validity.INVALID, error=str(exc) or type(exc).__name__)
                if isinstance(exc, Exception) and not isinstance(exc, DiagnosticError):
                    self.connected = False
                    self.last_error = str(exc) or type(exc).__name__
                    self._invalidate_all(self.last_error)
                    raise DiagnosticError(self.last_error) from exc
                raise
            finally:
                self._pending = None
                self._pending_version = None
                if not future.done():
                    future.cancel()
                elif not future.cancelled():
                    # Retrieve any exception also when send() failed concurrently.
                    future.exception()

    def _fail_pending(self, message: str) -> None:
        if self._pending is not None and not self._pending[1].done():
            self._pending[1].set_exception(DiagnosticError(message))

    async def _receive(self) -> None:
        try:
            while True:
                message = await self.transport.receive()
                if not isinstance(message, bytes):
                    self._log("rx_text", text=message)
                    continue
                self._log("rx", raw_hex=message.hex(" "))
                frames, errors = self._decoder.feed(message)
                if errors:
                    self._invalidate_all("; ".join(errors))
                for error in errors:
                    self._log("invalid_frame", reason=error)
                for frame in frames:
                    self._handle(frame)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.connected = False
            self.last_error = str(exc) or type(exc).__name__
            self._invalidate_all(self.last_error)
            self._fail_pending(self.last_error)
            try:
                self._log("receive_error", error=self.last_error)
            except Exception:
                pass  # Capacity/storage failure is retained in last_error.

    def _handle(self, frame: Frame) -> None:
        self._log("frame", command=frame.command, control=frame.control, raw_hex=frame.raw.hex(" "))
        if frame.command not in ReadCommand._value2member_map_ or frame.control != 0:
            self._log("unmatched_frame", reason="command or control does not match a verified read")
            return
        command = ReadCommand(frame.command)
        try:
            value = decode_read(command, frame.payload)
        except ValueError as exc:
            self._values[command] = Observation(self.session_id, Validity.INVALID, error=str(exc))
            self._log("invalid_payload", command=command.value, reason=str(exc))
            return
        if command == ReadCommand.VERSION and self._pending is not None and self._pending[0] == command:
            if value.type_index != self._pending_version:
                self._log("unmatched_firmware_subtype", received=value.type_index, expected=self._pending_version)
                return
        if command in self._tainted:
            self._log("late_response", command=command.value)
            return
        self._values[command] = Observation(self.session_id, Validity.VALID, value, self.clock())
        if self._pending is not None and self._pending[0] == command:
            future = self._pending[1]
            if not future.done():
                future.set_result(self._values[command])

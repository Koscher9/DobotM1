"""Async WebSocket client plus a Tkinter-friendly background thread."""

from __future__ import annotations

import asyncio
import threading
from collections import defaultdict, deque
from concurrent.futures import Future
from typing import Any, Callable

import websockets
from websockets.exceptions import ConnectionClosed

from config import COMMAND_TIMEOUT_S, CONNECT_TIMEOUT_S, DOBOT_URI, JOG_ACCEL_RATIO, JOG_VELOCITY_RATIO
from dobot.logger import FrameLogger
from dobot.protocol import (
    CMD_ALARMS,
    CMD_FIRMWARE_MODE,
    CMD_GET_POSE,
    CMD_JOG,
    CMD_JOG_COMMON_PARAMS,
    CMD_JOG_JOINT_PARAMS,
    CMD_QUEUED_CLEAR,
    Pose,
    jog_command,
    nonzero_alarm_bytes,
    pack_dobot_cmd,
    pack_jog,
    pack_jog_common_params,
    pack_jog_joint_params,
    parse_frames,
    unpack_alarms,
    unpack_pose,
)


class DobotError(RuntimeError):
    pass


class DobotClient:
    def __init__(
        self,
        uri: str = DOBOT_URI,
        logger: FrameLogger | None = None,
        command_timeout: float = COMMAND_TIMEOUT_S,
    ):
        self.uri = uri
        self.logger = logger
        self.command_timeout = command_timeout
        self.ws: Any = None
        self._reader_task: asyncio.Task[None] | None = None
        self._waiters: dict[int, deque[asyncio.Future]] = defaultdict(deque)
        self._request_locks: dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)
        self.last_alarms: bytes | None = None

    @property
    def connected(self) -> bool:
        if self.ws is None:
            return False
        state = getattr(self.ws, "state", None)
        if state is not None:
            name = getattr(state, "name", str(state))
            return name.endswith("OPEN")
        return bool(getattr(self.ws, "open", False))

    async def connect(self) -> None:
        if self.connected:
            raise DobotError("Bereits verbunden")
        if self.ws is not None:
            await self.close()
        try:
            self.ws = await websockets.connect(
                self.uri,
                ping_interval=None,
                ping_timeout=None,
                open_timeout=CONNECT_TIMEOUT_S,
            )
        except Exception as exc:
            if self.logger:
                self.logger.log_connect(self.uri, False, str(exc))
            raise
        if self.logger:
            self.logger.log_connect(self.uri, True)
        self._reader_task = asyncio.create_task(self._reader_loop(), name="dobot-reader")
        try:
            await self._prepare_mode1()
        except BaseException:
            try:
                await asyncio.shield(self.close())
            except Exception as cleanup_error:
                if self.logger:
                    self.logger.log_error("connect_cleanup", str(cleanup_error))
            raise

    async def close(self) -> None:
        ws = self.ws
        if ws is None:
            return
        try:
            await self.stop_jog()
        except Exception as exc:
            if self.logger:
                self.logger.log_error("stop_on_close", str(exc))
        if self._reader_task:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
            self._reader_task = None
        self._fail_waiters("disconnected")
        try:
            await ws.close()
        except Exception as exc:
            if self.logger:
                self.logger.log_error("close", str(exc))
            raise DobotError(f"WebSocket sauber schließen fehlgeschlagen: {exc}") from exc
        finally:
            self.ws = None
        if self.logger:
            self.logger.log_disconnect("client_close")

    async def get_pose(self) -> Pose:
        frame = await self.request(CMD_GET_POSE, b"", is_rw=0)
        pose = unpack_pose(frame.payload)
        if pose is None:
            raise DobotError(
                f"Ungültige Pose-Antwort: erwartet 32 endliche Datenbytes, "
                f"erhalten {len(frame.payload)}"
            )
        return pose

    async def get_alarms(self) -> bytes:
        self.last_alarms = None
        frame = await self.request(CMD_ALARMS, b"", is_rw=0)
        alarms = unpack_alarms(frame.payload)
        if alarms is None:
            raise DobotError(
                f"Ungültige CMD-20-Antwort: erwartet 32 Alarmbytes, "
                f"erhalten {len(frame.payload)}"
            )
        self.last_alarms = alarms
        return alarms

    async def clear_alarms(self) -> None:
        await self.send(CMD_ALARMS, b"\x00" * 32, is_rw=1)
        await asyncio.sleep(0.05)
        await self.get_alarms()

    async def set_jog_ratios(self, velocity_ratio: float, accel_ratio: float) -> None:
        await self.send(CMD_JOG_COMMON_PARAMS, pack_jog_common_params(velocity_ratio, accel_ratio), is_rw=1)

    async def jog(self, is_joint: bool, axis_index: int, positive: bool) -> None:
        if self.last_alarms is None or len(self.last_alarms) != 32:
            raise DobotError("CMD-20-Alarmstatus unbekannt; Jog gesperrt.")
        if any(self.last_alarms):
            raise DobotError(
                "CMD-20 enthält nicht-null Alarm-Rohbytes "
                f"({nonzero_alarm_bytes(self.last_alarms)}); "
                "Jog gesperrt. Ursache am Controller klären."
            )
        cmd = jog_command(axis_index, positive)
        await self.send(CMD_JOG, pack_jog(is_joint, cmd), is_rw=1, is_que=0)

    async def stop_jog(self) -> None:
        errors = []
        for is_joint in (True, False):
            try:
                await self.send(CMD_JOG, pack_jog(is_joint, 0), is_rw=1, is_que=0)
            except Exception as exc:
                errors.append(exc)
        if errors:
            raise DobotError(f"Jog-Stopp fehlgeschlagen: {errors[0]}") from errors[0]

    async def emergency_stop(self) -> None:
        errors = []
        try:
            await self.stop_jog()
        except Exception as exc:
            errors.append(exc)
        try:
            await self.send(CMD_QUEUED_CLEAR, b"", is_rw=1)
        except Exception as exc:
            errors.append(exc)
        if errors:
            raise DobotError(f"NOT-HALT unvollständig: {errors[0]}") from errors[0]

    async def send(self, cmd_id: int, payload: bytes = b"", is_rw: int = 1, is_que: int = 0) -> None:
        if not self.connected:
            raise DobotError("Nicht verbunden")
        raw = pack_dobot_cmd(cmd_id, payload, is_rw=is_rw, is_que=is_que)
        if self.logger:
            self.logger.log_tx(raw)
        await self.ws.send(raw)

    async def request(self, cmd_id: int, payload: bytes = b"", is_rw: int = 0) -> Any:
        async with self._request_locks[cmd_id]:
            loop = asyncio.get_running_loop()
            fut: asyncio.Future = loop.create_future()
            self._waiters[cmd_id].append(fut)
            try:
                await self.send(cmd_id, payload, is_rw=is_rw)
                return await asyncio.wait_for(fut, timeout=self.command_timeout)
            except asyncio.TimeoutError as exc:
                if self.logger:
                    self.logger.log_error("request_timeout", f"cmd {cmd_id}", cmd_id=cmd_id)
                raise DobotError(f"Keine Antwort auf CMD {cmd_id}") from exc
            finally:
                self._drop_waiter(cmd_id, fut)

    async def _prepare_mode1(self) -> None:
        await self.send(CMD_FIRMWARE_MODE, b"\x01\x01", is_rw=1)
        await asyncio.sleep(0.05)
        await self.send(CMD_JOG_JOINT_PARAMS, pack_jog_joint_params(), is_rw=1)
        await self.set_jog_ratios(JOG_VELOCITY_RATIO, JOG_ACCEL_RATIO)

    async def _reader_loop(self) -> None:
        assert self.ws is not None
        try:
            async for message in self.ws:
                if self.logger:
                    self.logger.log_rx(message)
                if not isinstance(message, (bytes, bytearray)):
                    continue
                for frame in parse_frames(bytes(message)):
                    if not frame.checksum_ok:
                        if self.logger:
                            self.logger.log_error(
                                "invalid_checksum", f"cmd {frame.cmd_id}", cmd_id=frame.cmd_id
                            )
                        continue
                    waiters = self._waiters.get(frame.cmd_id)
                    if waiters:
                        fut = waiters.popleft()
                        if not fut.done():
                            fut.set_result(frame)
            self._fail_waiters("WebSocket-Verbindung wurde geschlossen")
        except asyncio.CancelledError:
            raise
        except ConnectionClosed as exc:
            if self.logger:
                self.logger.log_disconnect(str(exc))
            self._fail_waiters(str(exc))
        except Exception as exc:
            if self.logger:
                self.logger.log_error("reader", str(exc))
            self._fail_waiters(str(exc))

    def _drop_waiter(self, cmd_id: int, fut: asyncio.Future) -> None:
        queue = self._waiters.get(cmd_id)
        if not queue:
            return
        try:
            queue.remove(fut)
        except ValueError:
            pass

    def _fail_waiters(self, message: str) -> None:
        for queue in self._waiters.values():
            while queue:
                fut = queue.popleft()
                if not fut.done():
                    fut.set_exception(DobotError(message))
        self._waiters.clear()


class DobotThread:
    """Owns an asyncio loop so Tkinter can call the client without blocking."""

    def __init__(self, uri: str = DOBOT_URI, logger: FrameLogger | None = None):
        self.uri = uri
        self.logger = logger
        self.client = DobotClient(uri=uri, logger=logger)
        self.loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run, name="dobot-ws", daemon=True)
        self._started = threading.Event()

    def start(self) -> None:
        if self._thread.is_alive():
            return
        self._thread.start()
        self._started.wait(timeout=2.0)

    def stop(self) -> None:
        if self.loop.is_running():
            try:
                self.submit(self.client.close()).result(timeout=3.0)
            except Exception as exc:
                if self.logger:
                    self.logger.log_error("thread_stop", str(exc))
            self.loop.call_soon_threadsafe(self.loop.stop)
        self._thread.join(timeout=3.0)

    def submit(self, coro) -> Future:
        if not self.loop.is_running():
            raise DobotError("Hintergrund-Loop läuft nicht")
        return asyncio.run_coroutine_threadsafe(coro, self.loop)

    def call(self, coro, timeout: float = 5.0):
        return self.submit(coro).result(timeout=timeout)

    def on_done(self, coro, callback: Callable[[Future], None]) -> Future:
        fut = self.submit(coro)
        fut.add_done_callback(callback)
        return fut

    def _run(self) -> None:
        asyncio.set_event_loop(self.loop)
        self._started.set()
        self.loop.run_forever()
        pending = asyncio.all_tasks(self.loop)
        for task in pending:
            task.cancel()
        if pending:
            self.loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        self.loop.close()

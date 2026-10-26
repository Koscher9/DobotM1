import asyncio
import json
import struct
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, patch

from dobot.logger import FrameLogger
from dobot.protocol import CMD_ALARMS, CMD_GET_POSE, pack_dobot_cmd, parse_frame
from tools.probe import probe


class FakeWebSocket:
    def __init__(self, pose_payload: bytes, alarm_payload: bytes):
        self.pose_payload = pose_payload
        self.alarm_payload = alarm_payload
        self.messages: asyncio.Queue[bytes] = asyncio.Queue()

    async def send(self, raw: bytes) -> None:
        command = parse_frame(raw)
        if command is None:
            raise AssertionError("probe sent malformed command")
        if command.cmd_id == CMD_GET_POSE:
            pose = pack_dobot_cmd(CMD_GET_POSE, self.pose_payload, is_rw=0)
            alarms = pack_dobot_cmd(CMD_ALARMS, self.alarm_payload, is_rw=0)
            await self.messages.put(pose + alarms)
        elif command.cmd_id == CMD_ALARMS:
            await self.messages.put(
                pack_dobot_cmd(CMD_ALARMS, self.alarm_payload, is_rw=0)
            )

    async def recv(self) -> bytes:
        return await self.messages.get()

    async def close(self) -> None:
        return None


class ProbeUriTests(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_websocket_uri_without_network_access(self) -> None:
        with TemporaryDirectory() as directory:
            logger = FrameLogger(Path(directory) / "probe.jsonl")
            report = await probe("http://localhost:54321", 0, logger)

        self.assertFalse(report["ok"])
        self.assertEqual(report["failed_at"], "uri")

    async def test_rejects_malformed_port_without_network_access(self) -> None:
        with TemporaryDirectory() as directory:
            logger = FrameLogger(Path(directory) / "probe.jsonl")
            report = await probe("ws://localhost:99999", 0, logger)

        self.assertFalse(report["ok"])
        self.assertEqual(report["failed_at"], "uri")

    async def run_fake_probe(self, pose_payload: bytes, alarm_payload: bytes):
        ws = FakeWebSocket(pose_payload, alarm_payload)
        with TemporaryDirectory() as directory:
            logger = FrameLogger(Path(directory) / "probe.jsonl")
            with (
                patch("tools.probe.tcp_check", return_value={"ok": True, "error": None}),
                patch("tools.probe.websockets.connect", new=AsyncMock(return_value=ws)),
                patch("tools.probe.COMMAND_TIMEOUT_S", 0.01),
            ):
                return await probe("ws://localhost:54321", 0, logger)

    async def test_accepts_combined_frames_and_preserves_nonzero_alarm_warning(self) -> None:
        alarms = bytearray(32)
        alarms[8] = 0x25

        report = await self.run_fake_probe(struct.pack("<8f", *(1.0,) * 8), alarms)

        self.assertTrue(report["ok"])
        pose_step = next(step for step in report["steps"] if step["step"] == "cmd_10_pose")
        alarm_step = next(step for step in report["steps"] if step["step"] == "cmd_20_alarms")
        self.assertEqual([frame["cmd_id"] for frame in pose_step["incoming"]], [10, 20])
        self.assertEqual(alarm_step["alarm_bytes"], "[8]=0x25")
        self.assertEqual(alarm_step["motion_clearance"], "unknown")
        self.assertIn("warning", alarm_step)

    async def test_rejects_short_pose_and_alarm_payloads(self) -> None:
        report = await self.run_fake_probe(bytes(31), bytes(31))

        self.assertFalse(report["ok"])
        self.assertEqual(report["failed_at"], "cmd_10_pose")
        pose_step = next(step for step in report["steps"] if step["step"] == "cmd_10_pose")
        alarm_step = next(step for step in report["steps"] if step["step"] == "cmd_20_alarms")
        self.assertIn("erwartet 32", pose_step["error"])
        self.assertIn("erwartet 32", alarm_step["error"])

    async def test_logger_records_metadata_for_concatenated_frames(self) -> None:
        pose = pack_dobot_cmd(CMD_GET_POSE, struct.pack("<8f", *(0.0,) * 8), is_rw=0)
        alarms = pack_dobot_cmd(CMD_ALARMS, bytes(32), is_rw=0)
        with TemporaryDirectory() as directory:
            path = Path(directory) / "frames.jsonl"
            FrameLogger(path).log_rx(pose + alarms)
            event = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual([frame["cmd_id"] for frame in event["frames"]], [10, 20])
        self.assertTrue(all(frame["checksum_ok"] for frame in event["frames"]))


if __name__ == "__main__":
    unittest.main()

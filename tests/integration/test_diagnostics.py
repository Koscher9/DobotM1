import asyncio
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

from dobot_m1.cli import DEMO_TRACE, parser, run
from dobot_m1.diagnostics import TraceLimitError, TraceRecorder
from dobot_m1.models import Validity
from dobot_m1.protocol import ReadCommand
from dobot_m1.replay import ReplayTransport, load_trace
from dobot_m1.session import DiagnosticError, ReadOnlySession
from dobot_m1.transports.websocket import WebSocketTransport
from tests.helpers import FakeTransport, alarm_reply, normal_responder


class DiagnosticTests(unittest.IsolatedAsyncioTestCase):
    async def test_demo_and_exported_replay_never_construct_live_transport(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch("dobot_m1.cli.WebSocketTransport", side_effect=AssertionError("no network allowed")):
                report, path = await run(parser().parse_args(["demo", "--output", str(root / "demo")]))
                self.assertTrue(report["ok"])
                self.assertTrue(report["synthetic"])
                self.assertFalse(report["motion_available"])
                trace = path.with_suffix(".jsonl")
                replay, _ = await run(parser().parse_args(["replay", str(trace), "--output", str(root / "replay")]))
                self.assertTrue(replay["ok"])
                self.assertIsNone(replay["synthetic"])
                self.assertEqual(replay["data_origin"], "recorded_unverified")
                self.assertEqual(replay["samples"][0]["pose"]["value"], report["samples"][0]["pose"]["value"])
            with zipfile.ZipFile(path.with_suffix(".zip")) as archive:
                self.assertEqual(archive.read("frames.jsonl"), trace.read_bytes())
                self.assertEqual(json.loads(archive.read("report.json"))["application_version"], "0.1.0")

    async def test_live_diagnosis_requires_explicit_uri(self):
        args = parser().parse_args(["diagnose"])
        with patch("dobot_m1.cli.WebSocketTransport", side_effect=AssertionError("no network allowed")):
            with self.assertRaisesRegex(ValueError, "explicit"):
                await run(args)

    async def test_profile_does_not_create_a_device_verification(self):
        with tempfile.TemporaryDirectory() as directory:
            profile = Path(directory) / "m1.toml"
            profile.write_text('[connection]\nuri="ws://unused.invalid:54321"\n[device]\nidentity_status="unverified"\n', encoding="utf-8")
            args = parser().parse_args(["diagnose", "--profile", str(profile), "--output", directory])
            fake = FakeTransport(normal_responder)
            with patch("dobot_m1.cli.WebSocketTransport", return_value=fake):
                report, _ = await run(args)
            self.assertTrue(report["ok"])
            self.assertEqual(report["device_profile"]["provided"]["identity_status"], "unverified")
            self.assertFalse(report["device_profile"]["verified_on_device"])
            self.assertEqual([raw[3] for raw in fake.sent], [10, 20])

    async def test_failed_connect_still_exports_diagnostic_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            fake = FakeTransport()
            fake.connect = AsyncMock(side_effect=ConnectionError("not reachable"))
            args = parser().parse_args(["diagnose", "--uri", "ws://unused.invalid", "--output", directory])
            with patch("dobot_m1.cli.WebSocketTransport", return_value=fake):
                report, path = await run(args)
            self.assertFalse(report["ok"])
            self.assertIn("not reachable", report["error"])
            self.assertTrue(path.with_suffix(".zip").exists())
            self.assertEqual(fake.sent, [])

    async def test_recording_capacity_failure_stops_session(self):
        with tempfile.TemporaryDirectory() as directory:
            recorder = TraceRecorder(Path(directory) / "limited.jsonl", max_bytes=256)
            fake = FakeTransport(normal_responder)
            session = ReadOnlySession(fake, recorder, timeout=0.04)
            await session.connect()
            try:
                with self.assertRaises(DiagnosticError):
                    await session.read(ReadCommand.POSE)
                self.assertFalse(session.connected)
                self.assertEqual(fake.sent, [])
            finally:
                with self.assertRaises(TraceLimitError):
                    await session.close()
                self.assertFalse(fake.open)

    async def test_websocket_adapter_only_opens_sends_given_read_and_closes(self):
        socket = AsyncMock()
        socket.recv.return_value = alarm_reply()
        with patch("websockets.asyncio.client.connect", new=AsyncMock(return_value=socket)) as connect:
            transport = WebSocketTransport("ws://unused.invalid:54321")
            await transport.connect()
            self.assertEqual(socket.send.await_count, 0)
            await transport.send(bytes.fromhex("AA AA 02 14 00 EC"))
            self.assertEqual(await transport.receive(), alarm_reply())
            await transport.close()
            socket.send.assert_awaited_once_with(bytes.fromhex("AA AA 02 14 00 EC"))
            self.assertIsNone(connect.await_args.kwargs["proxy"])
            socket.close.assert_awaited_once()

    async def test_replay_order_is_checked(self):
        transport = ReplayTransport(load_trace(DEMO_TRACE))
        await transport.connect()
        with self.assertRaisesRegex(RuntimeError, "order"):
            await transport.send(bytes.fromhex("AA AA 02 14 00 EC"))
        await transport.close()


class RecordingTests(unittest.TestCase):
    def test_full_raw_message_is_not_truncated_at_80_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "frames.jsonl"
            raw = bytes(range(256))
            TraceRecorder(path).record("rx", "session", raw_hex=raw.hex(" "))
            self.assertEqual(bytes.fromhex(json.loads(path.read_text())["raw_hex"]), raw)

    def test_recording_does_not_overwrite_existing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "frames.jsonl"
            TraceRecorder(path)
            with self.assertRaises(FileExistsError):
                TraceRecorder(path)

    def test_replay_rejects_writes_and_mixed_sessions(self):
        for contents in (
            [{"schema": 1, "event": "tx", "session_id": "one", "raw_hex": "aa aa 04 49 01 01 05 b0"}],
            [{"schema": 1, "event": "tx", "session_id": "one", "raw_hex": "aa aa 02 0a 00 f6"}, {"schema": 1, "event": "rx", "session_id": "two", "raw_hex": ""}],
        ):
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "trace.jsonl"
                path.write_text("\n".join(json.dumps(e) for e in contents), encoding="utf-8")
                with self.assertRaises(ValueError):
                    load_trace(path)

    def test_cli_rejects_nonfinite_timing_and_unbounded_samples(self):
        for flag, value in (("--timeout", "nan"), ("--max-age", "0"), ("--interval", "inf"), ("--samples", "10001")):
            with self.subTest(flag=flag), patch("sys.stderr"), self.assertRaises(SystemExit):
                parser().parse_args(["diagnose", "--uri", "ws://unused.invalid", flag, value])

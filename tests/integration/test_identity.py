import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from dobot_m1.cli import parser, run
from dobot_m1.controller import DiagnosticController
from dobot_m1.models import Validity
from dobot_m1.protocol import ReadCommand, decode_read, encode_read
from dobot_m1.session import DiagnosticError, ReadOnlySession, ReadTimeout
from tests.helpers import FakeTransport, alarm_reply, pose_reply, response


def identity_responder(raw):
    command = raw[3]
    if command == 0:
        return [response(0, b"SYNTHETIC-M1\0")]
    if command == 1:
        return [response(1, b"Synthetic device\0")]
    if command == 2:
        return [response(2, bytes((raw[5], 1, 4, 5)))]
    if command == 161:
        return [response(161, b"\x01\x01")]
    return [pose_reply() if command == 10 else alarm_reply(True)]


class IdentityProtocolTests(unittest.TestCase):
    def test_verified_identity_reads_always_have_control_zero(self):
        expected = {
            ReadCommand.SERIAL_NUMBER: "aa aa 02 00 00 00",
            ReadCommand.DEVICE_NAME: "aa aa 02 01 00 ff",
            ReadCommand.OPERATING_MODE: "aa aa 02 a1 00 5f",
        }
        for command, packet in expected.items():
            self.assertEqual(encode_read(command).hex(" "), packet)
        self.assertEqual(encode_read(ReadCommand.VERSION, 1).hex(" "), "aa aa 03 02 00 01 fd")
        for index in range(1, 9):
            raw = encode_read(ReadCommand.VERSION, index)
            self.assertEqual(raw[4], 0)
            self.assertEqual(sum(raw[3:]) & 255, 0)

    def test_arbitrary_payloads_and_version_subtypes_are_not_allowed(self):
        for value in (None, 0, 9, True, "1"):
            with self.assertRaises(ValueError):
                encode_read(ReadCommand.VERSION, value)
        with self.assertRaises(ValueError):
            encode_read(ReadCommand.POSE, 1)

    def test_missing_revision_is_not_fabricated_as_zero(self):
        version = decode_read(ReadCommand.VERSION, b"\x01\x01\x04")
        self.assertIsNone(version.revision)
        self.assertEqual(version.raw_hex, "01 01 04")

    def test_identity_text_rejects_control_bytes_and_bad_encoding(self):
        self.assertEqual(decode_read(ReadCommand.SERIAL_NUMBER, b"TEST\0").text, "TEST")
        for payload in (b"", b"\0", b"A\nB", b"\xff"):
            with self.assertRaises(ValueError):
                decode_read(ReadCommand.SERIAL_NUMBER, payload)

    def test_unrecognized_mode_is_preserved_without_inventing_a_mode(self):
        mode = decode_read(ReadCommand.OPERATING_MODE, b"\xfa\x00")
        self.assertEqual(mode.mode, 250)
        self.assertEqual(mode.name, "unrecognized")


class IdentitySessionTests(unittest.IsolatedAsyncioTestCase):
    async def test_controller_identity_scan_has_no_writes_or_mode_changes(self):
        transport = FakeTransport(identity_responder)
        session = ReadOnlySession(transport, timeout=0.04)
        await session.connect()
        try:
            result = await DiagnosticController(session).identify()
            self.assertEqual(result["status"], "read")
            self.assertFalse(result["motion_available"])
            self.assertEqual(result["observations"]["operating_mode"]["value"]["mode"], 1)
            self.assertEqual(len(result["firmware_versions"]), 8)
            self.assertEqual([p[3] for p in transport.sent], [0, 1, 161] + [2] * 8)
            self.assertTrue(all(p[4] == 0 for p in transport.sent))
        finally:
            await session.close()
        self.assertEqual(len(transport.sent), 11)

    async def test_version_response_must_match_requested_subtype(self):
        transport = FakeTransport(lambda raw: [response(2, b"\x01\x01\x04\x06"), response(2, b"\x03\x01\x04\x05")])
        session = ReadOnlySession(transport, timeout=0.04)
        await session.connect()
        try:
            observation = await session.read(ReadCommand.VERSION, 3)
            self.assertEqual(observation.value.type_index, 3)
        finally:
            await session.close()

    async def test_one_timed_out_version_taints_all_subtypes_until_reconnect(self):
        transport = FakeTransport()
        session = ReadOnlySession(transport, timeout=0.02)
        await session.connect()
        try:
            with self.assertRaises(ReadTimeout):
                await session.read(ReadCommand.VERSION, 1)
            with self.assertRaisesRegex(DiagnosticError, "reconnect"):
                await session.read(ReadCommand.VERSION, 3)
            self.assertEqual(len(transport.sent), 1)
        finally:
            await session.close()

    async def test_partial_identity_scan_does_not_claim_support_or_change_state(self):
        transport = FakeTransport(lambda raw: [] if raw[3] == 2 else identity_responder(raw))
        session = ReadOnlySession(transport, timeout=0.02)
        await session.connect()
        try:
            result = await DiagnosticController(session).identify()
            self.assertEqual(result["status"], "partial")
            self.assertIn("firmware_1", result["errors"])
            self.assertEqual(sum(p[3] == 2 for p in transport.sent), 1)
            self.assertTrue(all(p[4] == 0 for p in transport.sent))
        finally:
            await session.close()

    async def test_cli_identity_trace_can_be_replayed_offline(self):
        with tempfile.TemporaryDirectory() as directory:
            args = parser().parse_args(["identify", "--uri", "ws://unused.invalid", "--output", directory])
            fake = FakeTransport(identity_responder)
            with patch("dobot_m1.cli.WebSocketTransport", return_value=fake):
                report, path = await run(args)
            self.assertTrue(report["ok"])
            self.assertEqual(report["samples"][0]["identity"]["status"], "read")
            self.assertEqual(len(fake.sent), 13)
            replay_args = parser().parse_args(["replay", str(path.with_suffix(".jsonl")), "--output", str(Path(directory) / "replay")])
            with patch("dobot_m1.cli.WebSocketTransport", side_effect=AssertionError("No live transport during replay")):
                replay, _ = await run(replay_args)
            self.assertTrue(replay["ok"])
            left = report["samples"][0]["identity"]
            right = replay["samples"][0]["identity"]
            self.assertEqual(left["observations"]["serial_number"]["value"], right["observations"]["serial_number"]["value"])

import json
import tempfile
import unittest
from unittest.mock import patch

from dobot_m1.cli import parser, run
from dobot_m1.controller import DiagnosticController
from dobot_m1.protocol import ReadCommand
from dobot_m1.session import ReadOnlySession
from tests.helpers import FakeTransport, alarm_reply


class FailureRegressionTests(unittest.IsolatedAsyncioTestCase):
    async def test_incomplete_corrupt_pose_length_does_not_poison_following_alarm(self):
        transport = FakeTransport(lambda raw: [b"\xaa\xaa\xff\x0a\x00"] if raw[3] == 10 else [alarm_reply(True)])
        session = ReadOnlySession(transport, timeout=0.02)
        await session.connect()
        try:
            sample = await DiagnosticController(session).diagnose()
            self.assertEqual(sample["pose"]["validity"], "invalid")
            self.assertEqual(sample["alarms"]["validity"], "valid")
        finally:
            await session.close()

    async def test_live_sampling_stops_after_first_failed_cycle(self):
        with tempfile.TemporaryDirectory() as directory:
            args = parser().parse_args(["diagnose", "--uri", "ws://unused.invalid", "--samples", "100", "--timeout", "0.02", "--output", directory])
            transport = FakeTransport(lambda raw: [] if raw[3] == 10 else [alarm_reply()])
            with patch("dobot_m1.cli.WebSocketTransport", return_value=transport):
                report, _ = await run(args)
            self.assertFalse(report["ok"])
            self.assertEqual(len(report["samples"]), 1)
            self.assertEqual([r[3] for r in transport.sent], [10, 20])

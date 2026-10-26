import asyncio
import struct
import unittest

from dobot_m1.controller import DiagnosticController
from dobot_m1.models import Validity
from dobot_m1.protocol import ReadCommand
from dobot_m1.session import DiagnosticError, ReadOnlySession, ReadTimeout
from tests.helpers import FakeTransport, alarm_reply, normal_responder, pose_reply, response


class SessionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.transport = FakeTransport(normal_responder)
        self.session = ReadOnlySession(self.transport, timeout=0.04)
        await self.session.connect()

    async def asyncTearDown(self):
        await self.session.close()

    async def test_connect_and_close_send_nothing(self):
        await self.session.close()
        self.assertEqual(self.transport.sent, [])

    async def test_entire_diagnosis_sends_only_exact_pose_and_alarm_reads(self):
        result = await DiagnosticController(self.session).diagnose()
        self.assertEqual(self.transport.sent, [bytes.fromhex("AA AA 02 0A 00 F6"), bytes.fromhex("AA AA 02 14 00 EC")])
        self.assertEqual(result["pose"]["value"]["j3_mm"], 100)
        self.assertFalse(result["motion_available"])
        self.assertEqual(result["identity"]["status"], "not_queried")

    async def test_combined_frames_do_not_replace_explicit_new_alarm_read(self):
        self.transport.responder = lambda raw: [pose_reply() + alarm_reply()] if raw[3] == 10 else [alarm_reply(True)]
        result = await DiagnosticController(self.session).diagnose()
        self.assertEqual(result["alarms"]["value"]["nonzero_bytes"], {"8": 37})

    async def test_write_ack_and_short_payload_cannot_satisfy_read(self):
        self.transport.responder = lambda raw: [response(20, b"", 1), response(20, bytes(31)), alarm_reply(True)]
        observation = await self.session.read(ReadCommand.ALARMS)
        self.assertEqual(observation.value.raw[8], 0x25)

    async def test_bad_checksum_followed_by_valid_response(self):
        corrupt = bytearray(pose_reply()); corrupt[-1] ^= 1
        self.transport.responder = lambda raw: [bytes(corrupt), pose_reply()]
        result = await self.session.read(ReadCommand.POSE)
        self.assertEqual(result.validity, Validity.VALID)

    async def test_pose_timeout_still_reads_alarms_and_late_pose_is_not_reused(self):
        self.transport.responder = lambda raw: [] if raw[3] == 10 else [pose_reply() + alarm_reply(True)]
        result = await DiagnosticController(self.session).diagnose()
        self.assertEqual([r[3] for r in self.transport.sent], [10, 20])
        self.assertEqual(result["pose"]["validity"], "invalid")
        self.assertEqual(result["alarms"]["validity"], "valid")
        with self.assertRaisesRegex(DiagnosticError, "reconnect"):
            await self.session.read(ReadCommand.POSE)
        self.assertEqual(len(self.transport.sent), 2)

    async def test_invalid_alarm_payload_never_becomes_zero_alarm(self):
        self.transport.responder = lambda raw: [response(20, bytes(31))]
        with self.assertRaises(ReadTimeout):
            await self.session.read(ReadCommand.ALARMS)
        result = self.session.observation(ReadCommand.ALARMS)
        self.assertEqual(result.validity, Validity.INVALID)
        self.assertIsNone(result.value)

    async def test_cancelled_read_requires_new_session_before_repeating(self):
        self.transport.responder = None
        task = asyncio.create_task(self.session.read(ReadCommand.POSE))
        await asyncio.sleep(0)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        with self.assertRaisesRegex(DiagnosticError, "reconnect"):
            await self.session.read(ReadCommand.POSE)

    async def test_reconnect_changes_identity_and_invalidates_old_zero_status(self):
        await self.session.read(ReadCommand.ALARMS)
        first = self.session.session_id
        await self.session.close()
        self.assertEqual(self.session.observation(ReadCommand.ALARMS).validity, Validity.INVALID)
        await self.session.connect()
        self.assertNotEqual(self.session.session_id, first)
        result = self.session.observation(ReadCommand.ALARMS)
        self.assertEqual(result.validity, Validity.UNKNOWN)
        self.assertIsNone(result.value)

    async def test_unsolicited_nonzero_alarm_updates_status(self):
        await self.session.read(ReadCommand.ALARMS)
        self.transport.incoming.put_nowait(alarm_reply(True))
        await asyncio.sleep(0)
        self.assertEqual(self.session.observation(ReadCommand.ALARMS).value.raw[8], 0x25)

    async def test_connection_loss_invalidates_all_data(self):
        await self.session.read(ReadCommand.ALARMS)
        self.transport.incoming.put_nowait(ConnectionError("simulated cable loss"))
        await asyncio.sleep(0)
        self.assertFalse(self.session.connected)
        self.assertEqual(self.session.observation(ReadCommand.ALARMS).validity, Validity.INVALID)
        self.assertIsNone(self.session.observation(ReadCommand.ALARMS).value)

    async def test_disconnect_immediately_after_reply_does_not_revive_cached_pose(self):
        self.transport.responder = lambda raw: [pose_reply(), ConnectionError("lost immediately after reply")]
        with self.assertRaises(DiagnosticError):
            await self.session.read(ReadCommand.POSE)
        self.assertEqual(self.session.observation(ReadCommand.POSE).validity, Validity.INVALID)

    async def test_one_normal_request_at_a_time(self):
        self.transport.responder = None
        first = asyncio.create_task(self.session.read(ReadCommand.POSE))
        second = asyncio.create_task(self.session.read(ReadCommand.ALARMS))
        await asyncio.sleep(0)
        self.assertEqual([r[3] for r in self.transport.sent], [10])
        self.transport.incoming.put_nowait(pose_reply())
        await first
        await asyncio.sleep(0)
        self.assertEqual([r[3] for r in self.transport.sent], [10, 20])
        self.transport.incoming.put_nowait(alarm_reply())
        await second

    async def test_close_while_reading_fails_waiter_without_writes(self):
        self.transport.responder = None
        task = asyncio.create_task(self.session.read(ReadCommand.ALARMS))
        await asyncio.sleep(0)
        await self.session.close()
        with self.assertRaises(DiagnosticError):
            await task
        self.assertEqual([r[3] for r in self.transport.sent], [20])

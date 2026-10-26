import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from dobot.client import DobotClient, DobotError
from dobot.protocol import (
    CMD_ALARMS,
    CMD_JOG,
    CMD_QUEUED_CLEAR,
)


class DobotClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_request_removes_waiter_when_send_fails(self) -> None:
        client = DobotClient()

        with self.assertRaises(DobotError):
            await client.request(10)

        self.assertFalse(client._waiters.get(10))

    async def test_emergency_stop_clears_queue_even_if_jog_stop_fails(self) -> None:
        client = DobotClient()
        client.stop_jog = AsyncMock(side_effect=DobotError("stop failed"))
        client.send = AsyncMock()

        with self.assertRaises(DobotError):
            await client.emergency_stop()

        client.send.assert_awaited_once_with(CMD_QUEUED_CLEAR, b"", is_rw=1)

    async def test_mode_setup_does_not_clear_robot_alarms(self) -> None:
        client = DobotClient()
        client.send = AsyncMock()
        client.set_jog_ratios = AsyncMock()

        with patch("dobot.client.asyncio.sleep", new=AsyncMock()):
            await client._prepare_mode1()

        self.assertFalse(
            any(call.args[0] == CMD_ALARMS for call in client.send.await_args_list)
        )

    async def test_downward_j3_jog_uses_native_command_without_local_alarm_guess(self) -> None:
        client = DobotClient()
        client.last_alarms = bytes(32)
        client.ws = SimpleNamespace(open=True)
        client.send = AsyncMock()

        await client.jog(is_joint=True, axis_index=2, positive=False)

        client.send.assert_awaited_once_with(
            CMD_JOG, b"\x01\x06", is_rw=1, is_que=0
        )

    async def test_jog_is_blocked_when_alarm_status_is_unknown(self) -> None:
        client = DobotClient()
        client.ws = SimpleNamespace(open=True)
        client.send = AsyncMock()

        with self.assertRaisesRegex(DobotError, "Alarmstatus unbekannt"):
            await client.jog(is_joint=True, axis_index=2, positive=False)

        client.send.assert_not_awaited()

    async def test_jog_is_blocked_when_alarm_payload_is_incomplete(self) -> None:
        client = DobotClient()
        client.last_alarms = bytes(31)
        client.ws = SimpleNamespace(open=True)
        client.send = AsyncMock()

        with self.assertRaisesRegex(DobotError, "Alarmstatus unbekannt"):
            await client.jog(is_joint=True, axis_index=2, positive=False)

        client.send.assert_not_awaited()

    async def test_jog_is_blocked_for_any_nonzero_raw_alarm_byte(self) -> None:
        client = DobotClient()
        client.last_alarms = bytes.fromhex("00 00 00 00 00 00 00 00 25 01") + bytes(22)
        client.ws = SimpleNamespace(open=True)
        client.send = AsyncMock()

        with self.assertRaisesRegex(DobotError, r"\[8\]=0x25, \[9\]=0x01"):
            await client.jog(is_joint=True, axis_index=2, positive=False)

        client.send.assert_not_awaited()

    async def test_alarm_status_starts_unknown(self) -> None:
        client = DobotClient()

        self.assertIsNone(client.last_alarms)

    async def test_rejects_short_alarm_response_without_fabricating_zero_bytes(self) -> None:
        client = DobotClient()
        client.request = AsyncMock(return_value=SimpleNamespace(payload=bytes(31)))

        with self.assertRaisesRegex(DobotError, "erhalten 31"):
            await client.get_alarms()

        self.assertIsNone(client.last_alarms)

if __name__ == "__main__":
    unittest.main()

import struct
import unittest

from dobot.protocol import (
    CMD_GET_POSE,
    CMD_ALARMS,
    nonzero_alarm_bytes,
    pack_dobot_cmd,
    parse_frame,
    parse_frames,
)


class FrameProtocolTests(unittest.TestCase):
    def test_round_trip_empty_read_command(self) -> None:
        raw = pack_dobot_cmd(CMD_GET_POSE, is_rw=0)

        self.assertEqual(raw, bytes.fromhex("AA AA 02 0A 00 F6"))
        frame = parse_frame(raw)
        if frame is None:
            self.fail("valid packed frame was rejected")
        self.assertEqual(frame.cmd_id, CMD_GET_POSE)
        self.assertEqual(frame.payload, b"")
        self.assertTrue(frame.checksum_ok)

    def test_rejects_truncated_and_trailing_bytes(self) -> None:
        raw = pack_dobot_cmd(CMD_GET_POSE, b"\x01\x02", is_rw=0)

        self.assertIsNone(parse_frame(raw[:-1]))
        self.assertIsNone(parse_frame(raw + b"\x00"))

    def test_reports_bad_checksum(self) -> None:
        raw = bytearray(pack_dobot_cmd(CMD_GET_POSE, is_rw=0))
        raw[-1] ^= 0x01

        frame = parse_frame(raw)

        if frame is None:
            self.fail("frame with an invalid checksum was rejected")
        self.assertFalse(frame.checksum_ok)

    def test_parses_concatenated_frames_from_single_message(self) -> None:
        pose_response = pack_dobot_cmd(CMD_GET_POSE, bytes(range(32)), is_rw=0)
        alarm_response = pack_dobot_cmd(CMD_ALARMS, bytes(32), is_rw=0)

        frames = parse_frames(pose_response + alarm_response)

        self.assertEqual([frame.cmd_id for frame in frames], [CMD_GET_POSE, CMD_ALARMS])
        self.assertTrue(all(frame.checksum_ok for frame in frames))

    def test_alarm_diagnostics_preserve_the_raw_nonzero_bytes(self) -> None:
        alarm_state = bytearray(32)
        alarm_state[6] = 0x0B
        alarm_state[8] = 0x25

        self.assertEqual(nonzero_alarm_bytes(alarm_state), "[6]=0x0B, [8]=0x25")

    def test_alarm_diagnostics_do_not_treat_missing_data_as_zero(self) -> None:
        self.assertEqual(nonzero_alarm_bytes(None), "Status unbekannt")

    def test_rejects_alarm_payloads_with_unexpected_length(self) -> None:
        from dobot.protocol import unpack_alarms

        self.assertIsNone(unpack_alarms(bytes(31)))
        self.assertIsNone(unpack_alarms(bytes(33)))
        self.assertEqual(unpack_alarms(bytes(32)), bytes(32))

    def test_pose_requires_exact_length_and_finite_values(self) -> None:
        from dobot.protocol import unpack_pose

        self.assertIsNone(unpack_pose(bytes(31)))
        self.assertIsNone(unpack_pose(bytes(33)))
        self.assertIsNone(unpack_pose(struct.pack("<8f", *(0.0,) * 7 + (float("nan"),))))
        self.assertIsNotNone(unpack_pose(struct.pack("<8f", *(0.0,) * 8)))


if __name__ == "__main__":
    unittest.main()

import math
import struct
import unittest

from dobot_m1.models import AlarmState, Observation, Pose, Validity
from dobot_m1.protocol import FrameDecoder, ReadCommand, decode_alarms, decode_pose, encode_read
from dobot_m1.transports.websocket import validate_uri
from tests.helpers import POSE_VALUES, alarm_reply, pose_reply, response


class ProtocolTests(unittest.TestCase):
    def test_only_two_exact_verified_requests(self):
        self.assertEqual(encode_read(ReadCommand.POSE).hex(" "), "aa aa 02 0a 00 f6")
        self.assertEqual(encode_read(ReadCommand.ALARMS).hex(" "), "aa aa 02 14 00 ec")
        for invalid in (73, 161, 245, 10, b"", None):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                encode_read(invalid)

    def test_multiple_and_split_messages(self):
        decoder = FrameDecoder()
        raw = pose_reply() + alarm_reply(True)
        self.assertEqual(decoder.feed(raw[:1])[0], [])
        self.assertEqual(decoder.feed(raw[1:30])[0], [])
        frames, errors = decoder.feed(raw[30:])
        self.assertEqual([f.command for f in frames], [10, 20])
        self.assertEqual(errors, [])

    def test_bad_checksum_and_noise_resynchronize_to_valid_frame(self):
        corrupt = bytearray(pose_reply()); corrupt[-1] ^= 1
        frames, errors = FrameDecoder().feed(b"noise" + bytes(corrupt) + alarm_reply())
        self.assertEqual([f.command for f in frames], [20])
        self.assertTrue(any("checksum" in e for e in errors))

    def test_invalid_small_length_recovers(self):
        frames, errors = FrameDecoder().feed(b"\xaa\xaa\x01" + pose_reply())
        self.assertEqual([f.command for f in frames], [10])
        self.assertTrue(errors)

    def test_corrupt_large_length_retains_bounded_incomplete_data(self):
        decoder = FrameDecoder()
        frames, _ = decoder.feed(b"\xaa\xaa\xff" + pose_reply())
        self.assertEqual(frames, [])
        self.assertLess(len(decoder.buffer), decoder.MAX_FRAME)
        decoder.clear()
        self.assertEqual(len(decoder.buffer), 0)

    def test_explicit_units_and_linear_j3(self):
        pose = decode_pose(struct.pack("<8f", *POSE_VALUES))
        self.assertEqual(pose.j3_mm, 100)
        self.assertEqual(pose.j1_deg, 10)
        self.assertEqual(pose.z_mm, 100)

    def test_rejects_short_long_and_nonfinite_pose(self):
        for payload in (bytes(31), bytes(33), struct.pack("<8f", *(math.nan,) * 8), struct.pack("<8f", *(math.inf,) * 8)):
            with self.assertRaises(ValueError):
                decode_pose(payload)

    def test_alarm_bytes_not_zero_padded_or_decoded_as_limit(self):
        for size in (0, 31, 33):
            with self.assertRaises(ValueError):
                decode_alarms(bytes(size))
        data = bytearray(32); data[8] = 0x25
        alarm = AlarmState(data); data[8] = 0
        self.assertEqual(alarm.as_dict()["nonzero_bytes"], {"8": 37})
        self.assertEqual(alarm.as_dict()["interpretation"], "unverified")

    def test_data_age_uses_observation_clock_not_display_time(self):
        sample = Observation("s", Validity.VALID, Pose(*POSE_VALUES), 10)
        self.assertEqual(sample.evaluated(11, 2).validity, Validity.VALID)
        self.assertEqual(sample.evaluated(13, 2).validity, Validity.STALE)
        self.assertEqual(sample.received_monotonic, 10)

    def test_uri_validation(self):
        for uri in ("http://localhost", "ws://", "ws://localhost:0", "ws://localhost:99999", "ws://u:p@localhost", "ws://localhost/#x"):
            with self.subTest(uri=uri), self.assertRaises(ValueError):
                validate_uri(uri)
        validate_uri("ws://192.168.50.150:54321")

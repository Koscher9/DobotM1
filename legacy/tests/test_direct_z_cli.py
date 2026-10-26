import argparse
import unittest

from dobot.client import DobotError
from tools.direct_z import jog_duration_ms, require_clear_alarm_bytes


class DirectZCliTests(unittest.TestCase):
    def test_accepts_bounded_jog_durations(self) -> None:
        self.assertEqual(jog_duration_ms("50"), 50)
        self.assertEqual(jog_duration_ms("150"), 150)
        self.assertEqual(jog_duration_ms("250"), 250)

    def test_rejects_out_of_range_and_nonfinite_durations(self) -> None:
        for value in ("0", "49", "251", "-1", "nan", "inf"):
            with self.subTest(value=value), self.assertRaises(argparse.ArgumentTypeError):
                jog_duration_ms(value)

    def test_direct_jog_requires_known_zero_alarm_bytes(self) -> None:
        require_clear_alarm_bytes(bytes(32))
        with self.assertRaisesRegex(DobotError, "Alarmstatus unbekannt"):
            require_clear_alarm_bytes(None)
        with self.assertRaisesRegex(DobotError, "Alarmstatus unbekannt"):
            require_clear_alarm_bytes(bytes(31))

    def test_direct_jog_refuses_nonzero_alarm_bytes(self) -> None:
        alarms = bytearray(32)
        alarms[8] = 0x25

        with self.assertRaisesRegex(DobotError, r"\[8\]=0x25"):
            require_clear_alarm_bytes(bytes(alarms))


if __name__ == "__main__":
    unittest.main()

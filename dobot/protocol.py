"""Dobot M1 binary WebSocket frames (little-endian)."""

from __future__ import annotations

import struct
from dataclasses import dataclass

HEADER = 0xAAAA

CMD_GET_POSE = 10
CMD_ALARMS = 20
CMD_JOG_JOINT_PARAMS = 70
CMD_JOG_COMMON_PARAMS = 72
CMD_JOG = 73
CMD_FIRMWARE_MODE = 161
CMD_QUEUED_CLEAR = 245

ALARM_Z_LOWER_LIMIT = 0x20
ALARM_STALL = 0x04
ALARM_STALL_AND_LIMIT = 0x24

# ProtocolJOGCmd (CMD 73): isJoint=1 joint space, isJoint=0 cartesian.
JOG_STOP = 0
JOG_PLUS = (1, 3, 5, 7)  # J1+/X+, J2+/Y+, J3+/Z+, J4+/R+
JOG_MINUS = (2, 4, 6, 8)

JOINT_AXES = ("J1", "J2", "J3", "J4")
CARTESIAN_AXES = ("X", "Y", "Z", "R")


@dataclass(frozen=True)
class Frame:
    cmd_id: int
    ctrl: int
    payload: bytes
    checksum_ok: bool
    raw: bytes

    @property
    def is_rw(self) -> int:
        return self.ctrl & 0x01

    @property
    def is_queued(self) -> int:
        return (self.ctrl >> 1) & 0x01


@dataclass(frozen=True)
class Pose:
    x: float
    y: float
    z: float
    r: float
    j1: float
    j2: float
    j3: float
    j4: float

    def as_dict(self) -> dict[str, float]:
        return {
            "X": self.x,
            "Y": self.y,
            "Z": self.z,
            "R": self.r,
            "J1": self.j1,
            "J2": self.j2,
            "J3": self.j3,
            "J4": self.j4,
        }


def pack_dobot_cmd(
    cmd_id: int,
    payload: bytes = b"",
    is_rw: int = 1,
    is_que: int = 0,
) -> bytes:
    ctrl = ((is_que & 0x01) << 1) | (is_rw & 0x01)
    data_len = len(payload) + 2
    head = struct.pack("<HBBB", HEADER, data_len, cmd_id, ctrl)
    body = head[3:] + payload
    checksum = (0 - sum(body)) & 0xFF
    return head + payload + bytes([checksum])


def checksum_for(cmd_id: int, ctrl: int, payload: bytes) -> int:
    body = bytes([cmd_id, ctrl]) + payload
    return (0 - sum(body)) & 0xFF


def parse_frame(raw: bytes) -> Frame | None:
    if not isinstance(raw, (bytes, bytearray)):
        return None
    if len(raw) < 6:
        return None
    if raw[0] != 0xAA or raw[1] != 0xAA:
        return None
    data_len = raw[2]
    cmd_id = raw[3]
    ctrl = raw[4]
    payload_len = max(data_len - 2, 0)
    expected = 5 + payload_len + 1
    if len(raw) < expected:
        payload = bytes(raw[5:-1]) if len(raw) > 5 else b""
        checksum = raw[-1] if raw else 0
        ok = False
    else:
        payload = bytes(raw[5 : 5 + payload_len])
        checksum = raw[5 + payload_len]
        ok = checksum == checksum_for(cmd_id, ctrl, payload)
    return Frame(cmd_id=cmd_id, ctrl=ctrl, payload=payload, checksum_ok=ok, raw=bytes(raw))


def unpack_pose(payload: bytes) -> Pose | None:
    if len(payload) < 32:
        return None
    values = struct.unpack("<8f", payload[:32])
    return Pose(*values)


def unpack_alarms(payload: bytes) -> bytes:
    if len(payload) >= 32:
        return payload[:32]
    return payload.ljust(32, b"\x00")


def alarm_byte8(alarms: bytes) -> int:
    if len(alarms) > 8:
        return alarms[8]
    return 0


def describe_alarm_byte8(value: int) -> str:
    if value == 0:
        return "OK"
    flags = []
    if value & ALARM_Z_LOWER_LIMIT:
        flags.append("Z-Endschalter unten")
    if value & ALARM_STALL:
        flags.append("Motorstall/Überstrom")
    leftover = value & ~(ALARM_Z_LOWER_LIMIT | ALARM_STALL)
    if leftover:
        flags.append(f"0x{value:02X}")
    return ", ".join(flags) if flags else f"0x{value:02X}"


def jog_command(axis_index: int, positive: bool) -> int:
    """axis_index 0..3 -> JOG cmd 1..8."""
    if axis_index < 0 or axis_index > 3:
        raise ValueError(f"axis_index out of range: {axis_index}")
    return (axis_index * 2) + (1 if positive else 2)


def pack_jog(is_joint: bool, cmd: int) -> bytes:
    return struct.pack("<BB", 1 if is_joint else 0, cmd)


def pack_jog_common_params(velocity_ratio: float, accel_ratio: float) -> bytes:
    return struct.pack("<ff", float(velocity_ratio), float(accel_ratio))


def pack_jog_joint_params(vel: float = 50.0, acc: float = 50.0) -> bytes:
    values = (float(vel),) * 4 + (float(acc),) * 4
    return struct.pack("<8f", *values)

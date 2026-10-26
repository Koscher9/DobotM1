"""Pure binary protocol. Only explicitly verified diagnostic reads exist."""

import math
import struct
from dataclasses import dataclass
from enum import IntEnum

from .models import AlarmState, DeviceText, FirmwareVersion, OperatingMode, Pose


class ReadCommand(IntEnum):
    SERIAL_NUMBER = 0
    DEVICE_NAME = 1
    VERSION = 2
    POSE = 10
    ALARMS = 20
    OPERATING_MODE = 161


@dataclass(frozen=True)
class Frame:
    command: int
    control: int
    payload: bytes
    raw: bytes


def encode_read(command: ReadCommand, version_index: int | None = None) -> bytes:
    """No generic write encoder and no caller-supplied payload/control bits."""
    if not isinstance(command, ReadCommand):
        raise ValueError("Only a verified ReadCommand is permitted")
    payload = b""
    if command == ReadCommand.VERSION:
        if type(version_index) is not int or not 1 <= version_index <= 8:
            raise ValueError("A verified firmware subtype from 1 to 8 is required")
        payload = bytes((version_index,))
    elif version_index is not None:
        raise ValueError("Firmware subtype is valid only for the version getter")
    body = bytes((command, 0)) + payload
    return b"\xaa\xaa" + bytes((len(body),)) + body + bytes(((-sum(body)) & 0xFF,))


def decode_pose(payload: bytes) -> Pose:
    if len(payload) != 32:
        raise ValueError(f"Pose requires 32 bytes, got {len(payload)}")
    values = struct.unpack("<8f", payload)
    if not all(math.isfinite(v) for v in values):
        raise ValueError("Pose contains a non-finite value")
    return Pose(*values)


def decode_alarms(payload: bytes) -> AlarmState:
    return AlarmState(payload)


FIRMWARE_NAMES = {1: "Dobot", 2: "3D Printing", 3: "Driver1", 4: "Driver2", 5: "Driver3", 6: "Driver4", 7: "EndEffector", 8: "FPGA"}
MODE_NAMES = {0: "unknown", 1: "Dobot Mode", 2: "3D Printing Mode", 3: "Offline Mode", 4: "Test Mode", 5: "Fault Mode"}


def decode_read(command: ReadCommand, payload: bytes):
    if command == ReadCommand.POSE:
        return decode_pose(payload)
    if command == ReadCommand.ALARMS:
        return decode_alarms(payload)
    if command in (ReadCommand.SERIAL_NUMBER, ReadCommand.DEVICE_NAME):
        if not payload or len(payload) > 253:
            raise ValueError("Invalid device text length")
        try:
            text = payload.split(b"\0", 1)[0].decode("utf-8", errors="strict")
        except UnicodeError as exc:
            raise ValueError("Invalid device text encoding") from exc
        if not text or not all(c.isprintable() for c in text):
            raise ValueError("Device text is empty or contains control characters")
        return DeviceText(text, payload.hex(" "))
    if command == ReadCommand.VERSION:
        if len(payload) not in (3, 4) or payload[0] not in FIRMWARE_NAMES:
            raise ValueError("Invalid firmware version payload")
        return FirmwareVersion(payload[0], FIRMWARE_NAMES[payload[0]], payload[1], payload[2], payload[3] if len(payload) == 4 else None, payload.hex(" "))
    if command == ReadCommand.OPERATING_MODE:
        if len(payload) not in (1, 2):
            raise ValueError("Expected one or two operating mode bytes")
        return OperatingMode(payload[0], MODE_NAMES.get(payload[0], "unrecognized"), payload[1] if len(payload) == 2 else None, payload.hex(" "))
    raise ValueError("Unverified read decoder")


class FrameDecoder:
    """Bounded stream decoder; handles multiple and cross-message frames.

    A plausible incomplete frame is retained until more bytes arrive or the
    request times out. It is never treated as a complete response. Corrupt
    lengths cannot grow the retained buffer beyond one protocol frame.
    """

    MAX_FRAME = 259  # 2-byte header, length byte, at most 255 data bytes, checksum

    def __init__(self) -> None:
        self.buffer = bytearray()

    def clear(self) -> None:
        self.buffer.clear()

    def feed(self, raw: bytes) -> tuple[list[Frame], list[str]]:
        self.buffer.extend(raw)
        frames: list[Frame] = []
        errors: list[str] = []
        while self.buffer:
            start = self.buffer.find(b"\xaa\xaa")
            if start < 0:
                tail = self.buffer[-1:] if self.buffer[-1] == 0xAA else b""
                errors.append("discarded bytes without a frame header")
                self.buffer[:] = tail
                break
            if start:
                del self.buffer[:start]
                errors.append("discarded bytes before a frame header")
            if len(self.buffer) < 3:
                break
            length = self.buffer[2]
            if length < 2:
                del self.buffer[0]
                errors.append("invalid frame length below 2")
                continue
            total = length + 4
            if len(self.buffer) < total:
                break
            candidate = bytes(self.buffer[:total])
            if sum(candidate[3:]) & 0xFF:
                del self.buffer[0]
                errors.append("invalid frame checksum")
                continue
            del self.buffer[:total]
            frames.append(Frame(candidate[3], candidate[4], candidate[5:-1], candidate))
        assert len(self.buffer) < self.MAX_FRAME
        return frames, errors

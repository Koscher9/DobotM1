"""Pure binary protocol. Only two verified read requests can be encoded."""

import math
import struct
from dataclasses import dataclass
from enum import IntEnum

from .models import AlarmState, Pose


class ReadCommand(IntEnum):
    POSE = 10
    ALARMS = 20


@dataclass(frozen=True)
class Frame:
    command: int
    control: int
    payload: bytes
    raw: bytes


def encode_read(command: ReadCommand) -> bytes:
    """No generic write encoder and no caller-supplied payload/control bits."""
    if not isinstance(command, ReadCommand):
        raise ValueError("Only a verified ReadCommand is permitted")
    return bytes((0xAA, 0xAA, 2, command, 0, (-command) & 0xFF))


def decode_pose(payload: bytes) -> Pose:
    if len(payload) != 32:
        raise ValueError(f"Pose requires 32 bytes, got {len(payload)}")
    values = struct.unpack("<8f", payload)
    if not all(math.isfinite(v) for v in values):
        raise ValueError("Pose contains a non-finite value")
    return Pose(*values)


def decode_alarms(payload: bytes) -> AlarmState:
    return AlarmState(payload)


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

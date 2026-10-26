"""Explicit units and immutable, session-scoped diagnostic observations."""

from dataclasses import asdict, dataclass, replace
from enum import StrEnum
from typing import Any


class Validity(StrEnum):
    UNKNOWN = "unknown"
    VALID = "valid"
    STALE = "stale"
    INVALID = "invalid"


@dataclass(frozen=True)
class Pose:
    x_mm: float
    y_mm: float
    z_mm: float
    r_deg: float
    j1_deg: float
    j2_deg: float
    j3_mm: float
    j4_deg: float


@dataclass(frozen=True)
class DeviceText:
    text: str
    raw_hex: str


@dataclass(frozen=True)
class FirmwareVersion:
    type_index: int
    component: str
    major: int
    minor: int
    revision: int | None
    raw_hex: str


@dataclass(frozen=True)
class OperatingMode:
    mode: int
    name: str
    controller_flag: int | None
    raw_hex: str


@dataclass(frozen=True)
class AlarmState:
    raw: bytes

    def __post_init__(self) -> None:
        if len(self.raw) != 32:
            raise ValueError("Expected exactly 32 alarm bytes")
        object.__setattr__(self, "raw", bytes(self.raw))

    def as_dict(self) -> dict[str, Any]:
        return {
            "raw_hex": self.raw.hex(" "),
            "nonzero_bytes": {str(i): b for i, b in enumerate(self.raw) if b},
            "interpretation": "unverified",
        }


@dataclass(frozen=True)
class Observation:
    session_id: str
    validity: Validity = Validity.UNKNOWN
    value: Pose | AlarmState | DeviceText | FirmwareVersion | OperatingMode | None = None
    received_monotonic: float | None = None
    error: str | None = None

    def evaluated(self, now: float, max_age: float) -> "Observation":
        if self.validity == Validity.VALID and self.received_monotonic is not None:
            if now - self.received_monotonic > max_age:
                return replace(self, validity=Validity.STALE)
        return self

    def as_dict(self, now: float) -> dict[str, Any]:
        value = self.value
        return {
            "session_id": self.session_id,
            "validity": self.validity.value,
            "age_s": None if self.received_monotonic is None else max(0, now - self.received_monotonic),
            "value": value.as_dict() if isinstance(value, AlarmState) else asdict(value) if value else None,
            "error": self.error,
        }

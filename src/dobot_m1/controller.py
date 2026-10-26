"""Read-only application boundary shared by the CLI and a future UI."""

from .protocol import ReadCommand
from .session import DiagnosticError, ReadOnlySession


class DiagnosticController:
    def __init__(self, session: ReadOnlySession) -> None:
        self.session = session

    async def diagnose(self) -> dict:
        errors = {}
        # One failed pose read must not prevent an independent alarm read.
        for command in (ReadCommand.POSE, ReadCommand.ALARMS):
            try:
                await self.session.read(command)
            except DiagnosticError as exc:
                errors[command.name.lower()] = str(exc)
        now = self.session.clock()
        return {
            "session_id": self.session.session_id,
            "connected": self.session.connected,
            "pose": self.session.observation(ReadCommand.POSE).as_dict(now),
            "alarms": self.session.observation(ReadCommand.ALARMS).as_dict(now),
            "errors": errors,
            "identity": {"status": "not_queried", "reason": "Use the explicit identify command for device and firmware reads"},
            "motion_available": False,
            "motion_reason": "This milestone provides diagnostics only; no motion API is implemented",
        }

    async def identify(self) -> dict:
        observations = {}
        versions = {}
        errors = {}
        for command in (ReadCommand.SERIAL_NUMBER, ReadCommand.DEVICE_NAME, ReadCommand.OPERATING_MODE):
            try:
                observations[command.name.lower()] = await self.session.read(command)
            except DiagnosticError as exc:
                errors[command.name.lower()] = str(exc)
        for index in range(1, 9):
            try:
                versions[str(index)] = await self.session.read(ReadCommand.VERSION, index)
            except DiagnosticError as exc:
                errors[f"firmware_{index}"] = str(exc)
                # One ambiguous version reply taints CMD 2 for every subtype.
                break
        now = self.session.clock()
        encode = lambda value: value.evaluated(now, self.session.max_age).as_dict(now)
        return {
            "status": "read" if not errors else "partial",
            "observations": {name: encode(value) for name, value in observations.items()},
            "firmware_versions": {name: encode(value) for name, value in versions.items()},
            "errors": errors,
            "motion_available": False,
        }

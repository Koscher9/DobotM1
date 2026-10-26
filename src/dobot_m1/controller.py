"""Read-only application boundary shared by the CLI and a future UI."""

from .protocol import ReadCommand
from .session import DiagnosticError, ReadOnlySession


class DiagnosticController:
    def __init__(self, session: ReadOnlySession) -> None:
        self.session = session

    async def diagnose(self) -> dict:
        errors = {}
        # One failed pose read must not prevent an independent alarm read.
        for command in ReadCommand:
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
            "identity": {"status": "not_queried", "reason": "No additional identity command verified for this device yet"},
            "motion_available": False,
            "motion_reason": "This milestone provides diagnostics only; no motion API is implemented",
        }

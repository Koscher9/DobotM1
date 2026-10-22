"""JSONL logger for Dobot WebSocket frames."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dobot.protocol import parse_frame


class FrameLogger:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, event: dict[str, Any]) -> None:
        event = {"ts": datetime.now(timezone.utc).isoformat(), **event}
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")

    def log_connect(self, uri: str, ok: bool, error: str | None = None) -> None:
        self.write({"type": "connect", "uri": uri, "ok": ok, "error": error})

    def log_disconnect(self, reason: str | None = None) -> None:
        self.write({"type": "disconnect", "reason": reason})

    def log_tx(self, raw: bytes) -> None:
        self.write(self._frame_event("tx", raw))

    def log_rx(self, raw: bytes | str) -> None:
        if isinstance(raw, str):
            self.write({"type": "rx", "kind": "text", "text": raw[:500]})
            return
        self.write(self._frame_event("rx", raw))

    def log_error(self, stage: str, error: str, **extra: Any) -> None:
        self.write({"type": "error", "stage": stage, "error": error, **extra})

    def log_note(self, message: str, **extra: Any) -> None:
        self.write({"type": "note", "message": message, **extra})

    @staticmethod
    def _frame_event(direction: str, raw: bytes) -> dict[str, Any]:
        parsed = parse_frame(raw)
        event: dict[str, Any] = {
            "type": direction,
            "len": len(raw),
            "hex": raw[:80].hex(" "),
        }
        if parsed is None:
            event["parse_error"] = "not a dobot frame"
            return event
        event.update(
            {
                "cmd_id": parsed.cmd_id,
                "ctrl": parsed.ctrl,
                "payload_len": len(parsed.payload),
                "checksum_ok": parsed.checksum_ok,
            }
        )
        return event

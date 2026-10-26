"""Complete bounded JSONL traces and a portable diagnostic archive."""

import json
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path


class TraceLimitError(RuntimeError):
    pass


class TraceRecorder:
    def __init__(self, path: Path, max_bytes: int = 16 * 1024 * 1024) -> None:
        if max_bytes < 256:
            raise ValueError("Trace capacity must be at least 256 bytes")
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Never overwrite a previous run, including on a filename collision.
        with self.path.open("x", encoding="utf-8"):
            pass
        self.max_bytes = max_bytes
        self._size = 0

    def record(self, event: str, session_id: str, **fields) -> None:
        data = {
            "schema": 1, "utc": datetime.now(timezone.utc).isoformat(),
            "monotonic_s": time.monotonic(), "session_id": session_id,
            "event": event, **fields,
        }
        raw = (json.dumps(data, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
        if self._size + len(raw) > self.max_bytes:
            raise TraceLimitError("Trace capacity reached; end this diagnostic run and export its data")
        with self.path.open("ab") as handle:
            handle.write(raw)
        self._size += len(raw)

    def export(self, target: Path, report: dict) -> None:
        with zipfile.ZipFile(target, "x", zipfile.ZIP_DEFLATED) as archive:
            archive.write(self.path, "frames.jsonl")
            archive.writestr("report.json", json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False))

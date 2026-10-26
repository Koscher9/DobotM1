"""Explicit live reads, offline demo and offline replay; no motion commands."""

import argparse
import asyncio
import json
import math
import platform
import sys
import tomllib
import uuid
from pathlib import Path

from . import __version__
from .controller import DiagnosticController
from .diagnostics import TraceRecorder
from .replay import ReplayTransport, load_trace
from .session import ReadOnlySession
from .transports.websocket import WebSocketTransport, validate_uri


DEMO_TRACE = Path(__file__).with_name("demo.jsonl")


def positive_seconds(value: str) -> float:
    number = float(value)
    if not math.isfinite(number) or not 0 < number <= 60:
        raise argparse.ArgumentTypeError("Expected finite seconds in (0, 60]")
    return number


def sample_count(value: str) -> int:
    number = int(value)
    if not 1 <= number <= 10000:
        raise argparse.ArgumentTypeError("Expected 1 to 10000 samples")
    return number


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Dobot M1: Diagnose ohne Bewegungsfunktionen")
    sub = result.add_subparsers(dest="mode", required=True)
    for name, help_text in (
        ("demo", "Offline-Demo mit kuenstlichen Antworten"),
        ("replay", "Aufzeichnung ausschliesslich offline wiedergeben"),
        ("diagnose", "Explizit eine lesende WebSocket-Diagnose starten"),
    ):
        command = sub.add_parser(name, help=help_text)
        command.add_argument("--output", type=Path, default=Path("diagnostics"))
        command.add_argument("--timeout", type=positive_seconds, default=1.5)
        command.add_argument("--max-age", type=positive_seconds, default=2.0)
        if name == "replay":
            command.add_argument("trace", type=Path)
        if name == "diagnose":
            command.add_argument("--uri")
            command.add_argument("--profile", type=Path)
            command.add_argument("--samples", type=sample_count, default=1)
            command.add_argument("--interval", type=positive_seconds, default=0.25)
    return result


async def run(args: argparse.Namespace) -> tuple[dict, Path]:
    profile: dict = {}
    uri = None
    samples = 1
    replay = None
    if args.mode == "diagnose":
        if args.profile:
            with args.profile.open("rb") as handle:
                profile = tomllib.load(handle)
        uri = args.uri or profile.get("connection", {}).get("uri")
        if not isinstance(uri, str) or not uri:
            raise ValueError("diagnose requires an explicit --uri or a configured profile URI")
        validate_uri(uri)
        transport = WebSocketTransport(uri)
        samples = args.samples
    else:
        events = load_trace(DEMO_TRACE if args.mode == "demo" else args.trace)
        replay = ReplayTransport(events)
        transport = replay
        # The diagnostic controller always attempts pose then alarms. Repeat
        # enough cycles to consume a trace, including cycles with failed reads.
        samples = max(1, sum(e["event"] == "tx" and bytes.fromhex(e["raw_hex"])[3] == 10 for e in events))
    args.output.mkdir(parents=True, exist_ok=True)
    token = uuid.uuid4().hex
    recorder = TraceRecorder(args.output / f"{token}.jsonl")
    session = ReadOnlySession(transport, recorder, args.timeout, args.max_age)
    report = {
        "schema": 1, "application_version": __version__, "python": platform.python_version(),
        "mode": args.mode,
        "synthetic": True if args.mode == "demo" else False if args.mode == "diagnose" else None,
        "data_origin": "synthetic" if args.mode == "demo" else "recorded_unverified" if args.mode == "replay" else "live_unverified",
        "uri": uri,
        "device_profile": {"provided": profile.get("device", {}), "verified_on_device": False},
        "samples": [], "ok": False, "motion_available": False,
        "capabilities": {"pose": "implemented_unverified_on_device", "alarms": "implemented_unverified_on_device", "identity": "not_queried"},
    }
    try:
        await session.connect()
        for index in range(samples):
            result = await DiagnosticController(session).diagnose()
            report["samples"].append(result)
            if result["errors"] or not result["connected"]:
                break
            if index + 1 < samples and args.mode == "diagnose":
                await asyncio.sleep(args.interval)
        report["ok"] = all(
            not sample["errors"] and sample["connected"]
            and all(sample[key]["validity"] == "valid" for key in ("pose", "alarms"))
            for sample in report["samples"]
        )
        if replay is not None and not replay.complete:
            raise ValueError("Trace was not fully consumed; the recorded sequence differs from diagnostic polling")
    except Exception as exc:
        report["ok"] = False
        report["error"] = str(exc) or type(exc).__name__
    finally:
        try:
            await session.close()
        except Exception as exc:
            report["ok"] = False
            report["close_error"] = str(exc) or type(exc).__name__
    report_path = args.output / f"{token}.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    recorder.export(args.output / f"{token}.zip", report)
    return report, report_path


def main(argv: list[str] | None = None) -> int:
    arguments = parser()
    args = arguments.parse_args(argv)
    try:
        report, path = asyncio.run(run(args))
    except KeyboardInterrupt:
        print("Diagnose abgebrochen; keine Bewegungsfunktion wurde gestartet.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"Diagnose fehlgeschlagen: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\nDiagnosebericht: {path}")
    print("Diagnose ist keine Bewegungsfreigabe. Diese Version besitzt keine Bewegungsfunktionen.")
    return 0 if report["ok"] else 1

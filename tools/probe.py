"""Diagnose TCP/WebSocket/Dobot frames without the UI."""

from __future__ import annotations

import argparse
import asyncio
import json
import socket
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import COMMAND_TIMEOUT_S, CONNECT_TIMEOUT_S, DOBOT_URI, LOG_DIR  # noqa: E402
from dobot.logger import FrameLogger  # noqa: E402
from dobot.protocol import (  # noqa: E402
    CMD_ALARMS,
    CMD_GET_POSE,
    nonzero_alarm_bytes,
    pack_dobot_cmd,
    parse_frame,
    parse_frames,
    unpack_pose,
    unpack_alarms,
)

try:
    import websockets
except ImportError:
    websockets = None  # type: ignore


def tcp_check(host: str, port: int, timeout: float) -> dict:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((host, port))
        return {"ok": True, "error": None}
    except OSError as exc:
        return {"ok": False, "error": str(exc)}
    finally:
        sock.close()


async def collect_frames(ws, seconds: float) -> list[bytes]:
    frames: list[bytes] = []
    loop = asyncio.get_running_loop()
    deadline = loop.time() + seconds
    while loop.time() < deadline:
        remaining = deadline - loop.time()
        if remaining <= 0:
            break
        try:
            message = await asyncio.wait_for(ws.recv(), timeout=remaining)
        except asyncio.TimeoutError:
            break
        if isinstance(message, (bytes, bytearray)):
            frames.append(bytes(message))
        else:
            frames.append(message.encode("utf-8", errors="replace"))
    return frames


def summarize_frame(raw: bytes) -> dict:
    parsed = parse_frame(raw)
    summary = {"len": len(raw), "hex": raw[:40].hex(" ")}
    if parsed is None:
        summary["parse_error"] = "not a dobot frame"
        return summary
    summary.update(
        {
            "cmd_id": parsed.cmd_id,
            "ctrl": parsed.ctrl,
            "payload_len": len(parsed.payload),
            "checksum_ok": parsed.checksum_ok,
        }
    )
    return summary


def summarize_messages(messages: list[bytes]) -> list[dict]:
    summaries = []
    for raw in messages:
        frames = parse_frames(raw)
        if frames:
            summaries.extend(summarize_frame(frame.raw) for frame in frames)
        else:
            summaries.append(summarize_frame(raw))
    return summaries


def find_response(messages: list[bytes], cmd_id: int):
    for raw in messages:
        for frame in parse_frames(raw):
            if frame.cmd_id == cmd_id:
                return frame
    return None


async def probe(uri: str, listen_s: float, logger: FrameLogger) -> dict:
    report: dict = {"uri": uri, "steps": []}
    try:
        parsed = urlparse(uri)
    except ValueError as exc:
        report["steps"].append({"step": "uri", "ok": False, "error": str(exc)})
        report["ok"] = False
        report["failed_at"] = "uri"
        return report
    host = parsed.hostname or ""
    try:
        port = parsed.port or (443 if parsed.scheme == "wss" else 80)
    except ValueError as exc:
        report["steps"].append({"step": "uri", "ok": False, "error": str(exc)})
        report["ok"] = False
        report["failed_at"] = "uri"
        return report
    if parsed.scheme not in ("ws", "wss") or not host or not 1 <= port <= 65535:
        report["steps"].append(
            {"step": "uri", "ok": False, "error": "URI muss ws:// oder wss:// mit gültigem Host/Port sein"}
        )
        report["ok"] = False
        report["failed_at"] = "uri"
        return report

    tcp = tcp_check(host, port, CONNECT_TIMEOUT_S)
    report["steps"].append({"step": "tcp", **tcp})
    logger.log_note("tcp", **tcp)
    if not tcp["ok"]:
        report["ok"] = False
        report["failed_at"] = "tcp"
        return report

    if websockets is None:
        report["ok"] = False
        report["failed_at"] = "import"
        report["steps"].append({"step": "websocket", "ok": False, "error": "websockets nicht installiert"})
        return report

    try:
        ws = await websockets.connect(
            uri,
            ping_interval=None,
            ping_timeout=None,
            open_timeout=CONNECT_TIMEOUT_S,
        )
    except Exception as exc:
        logger.log_connect(uri, False, str(exc))
        report["ok"] = False
        report["failed_at"] = "websocket"
        report["steps"].append({"step": "websocket", "ok": False, "error": str(exc)})
        return report

    logger.log_connect(uri, True)
    report["steps"].append({"step": "websocket", "ok": True})

    try:
        idle = await collect_frames(ws, listen_s)
        for raw in idle:
            logger.log_rx(raw)
        report["steps"].append(
            {
                "step": "idle_listen",
                "ok": True,
                "count": len(idle),
                "frames": summarize_messages(idle),
            }
        )

        pose_raw = pack_dobot_cmd(CMD_GET_POSE, b"", is_rw=0)
        logger.log_tx(pose_raw)
        await ws.send(pose_raw)
        pose_frames = await collect_frames(ws, COMMAND_TIMEOUT_S)
        for raw in pose_frames:
            logger.log_rx(raw)
        pose_match = find_response(pose_frames, CMD_GET_POSE)
        pose = unpack_pose(pose_match.payload) if pose_match and pose_match.checksum_ok else None
        pose_step = {
            "step": "cmd_10_pose",
            "ok": pose is not None,
            "incoming": summarize_messages(pose_frames),
        }
        if pose_match:
            pose_step["pose"] = pose.as_dict() if pose else None
            pose_step["checksum_ok"] = pose_match.checksum_ok
            if not pose_match.checksum_ok:
                pose_step["error"] = "ungültige Prüfsumme in CMD-10-Antwort"
            elif pose is None:
                pose_step["error"] = (
                    f"ungültige Pose-Payload: erwartet 32 endliche Datenbytes, "
                    f"erhalten {len(pose_match.payload)}"
                )
        else:
            pose_step["error"] = "keine CMD-10-Antwort"
        report["steps"].append(pose_step)

        alarm_raw = pack_dobot_cmd(CMD_ALARMS, b"", is_rw=0)
        logger.log_tx(alarm_raw)
        await ws.send(alarm_raw)
        alarm_frames = await collect_frames(ws, COMMAND_TIMEOUT_S)
        for raw in alarm_frames:
            logger.log_rx(raw)
        alarm_match = find_response(alarm_frames, CMD_ALARMS)
        alarms = (
            unpack_alarms(alarm_match.payload)
            if alarm_match and alarm_match.checksum_ok
            else None
        )
        alarm_step = {
            "step": "cmd_20_alarms",
            "ok": alarms is not None,
            "incoming": summarize_messages(alarm_frames),
        }
        if alarm_match:
            alarm_step["checksum_ok"] = alarm_match.checksum_ok
            if not alarm_match.checksum_ok:
                alarm_step["error"] = "ungültige Prüfsumme in CMD-20-Antwort"
            elif alarms is None:
                alarm_step["error"] = (
                    f"ungültige Alarm-Payload: erwartet 32 Bytes, "
                    f"erhalten {len(alarm_match.payload)}"
                )
            else:
                alarm_step["alarm_bytes"] = nonzero_alarm_bytes(alarms)
                alarm_step["has_nonzero_alarm_bytes"] = any(alarms)
                if any(alarms):
                    alarm_step["motion_clearance"] = "unknown"
                    alarm_step["warning"] = (
                        "Nicht-null CMD-20-Rohdaten sind keine interpretierte "
                        "Bewegungsfreigabe; Steuerungsanzeige prüfen."
                    )
                else:
                    alarm_step["motion_clearance"] = "unknown"
                    alarm_step["warning"] = (
                        "Nullbytes allein bestätigen keine Bewegungsfreigabe."
                    )
        else:
            alarm_step["error"] = "keine CMD-20-Antwort"
        report["steps"].append(alarm_step)
    finally:
        await ws.close()
        logger.log_disconnect("probe_done")

    failed_at = next(
        (step.get("step") for step in report["steps"] if not step.get("ok", True)),
        None,
    )
    report["ok"] = failed_at is None
    if failed_at is not None:
        report["failed_at"] = failed_at
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Dobot M1 Verbindungs- und Frame-Analyse")
    parser.add_argument("--uri", default=DOBOT_URI)
    parser.add_argument("--listen", type=float, default=1.0, help="Sekunden unaufgefordert zuhören")
    args = parser.parse_args()
    if args.listen < 0:
        parser.error("--listen muss mindestens 0 sein")

    log_path = ROOT / LOG_DIR / "probe.jsonl"
    logger = FrameLogger(log_path)
    report = asyncio.run(probe(args.uri, args.listen, logger))

    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\nFrame-Log: {log_path}")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

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
    alarm_byte8,
    describe_alarm_byte8,
    pack_dobot_cmd,
    parse_frame,
    unpack_pose,
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
    deadline = asyncio.get_event_loop().time() + seconds
    while asyncio.get_event_loop().time() < deadline:
        remaining = deadline - asyncio.get_event_loop().time()
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


async def probe(uri: str, listen_s: float, logger: FrameLogger) -> dict:
    report: dict = {"uri": uri, "steps": []}
    parsed = urlparse(uri)
    host = parsed.hostname or ""
    port = parsed.port or 80

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
                "frames": [summarize_frame(raw) for raw in idle],
            }
        )

        pose_raw = pack_dobot_cmd(CMD_GET_POSE, b"", is_rw=0)
        logger.log_tx(pose_raw)
        await ws.send(pose_raw)
        pose_frames = await collect_frames(ws, COMMAND_TIMEOUT_S)
        for raw in pose_frames:
            logger.log_rx(raw)
        pose_match = None
        for raw in pose_frames:
            frame = parse_frame(raw)
            if frame and frame.cmd_id == CMD_GET_POSE:
                pose_match = frame
                break
        pose_step = {
            "step": "cmd_10_pose",
            "ok": pose_match is not None,
            "incoming": [summarize_frame(raw) for raw in pose_frames],
        }
        if pose_match:
            pose = unpack_pose(pose_match.payload)
            pose_step["pose"] = pose.as_dict() if pose else None
            pose_step["checksum_ok"] = pose_match.checksum_ok
        else:
            pose_step["error"] = "keine CMD-10-Antwort"
        report["steps"].append(pose_step)

        alarm_raw = pack_dobot_cmd(CMD_ALARMS, b"", is_rw=0)
        logger.log_tx(alarm_raw)
        await ws.send(alarm_raw)
        alarm_frames = await collect_frames(ws, COMMAND_TIMEOUT_S)
        for raw in alarm_frames:
            logger.log_rx(raw)
        alarm_match = None
        for raw in alarm_frames:
            frame = parse_frame(raw)
            if frame and frame.cmd_id == CMD_ALARMS:
                alarm_match = frame
                break
        alarm_step = {
            "step": "cmd_20_alarms",
            "ok": alarm_match is not None,
            "incoming": [summarize_frame(raw) for raw in alarm_frames],
        }
        if alarm_match:
            byte8 = alarm_byte8(alarm_match.payload)
            alarm_step["byte8"] = byte8
            alarm_step["byte8_hex"] = f"0x{byte8:02X}"
            alarm_step["meaning"] = describe_alarm_byte8(byte8)
        else:
            alarm_step["error"] = "keine CMD-20-Antwort"
        report["steps"].append(alarm_step)
    finally:
        await ws.close()
        logger.log_disconnect("probe_done")

    failed = next((step for step in report["steps"] if not step.get("ok", True)), None)
    report["ok"] = failed is None
    if failed:
        report["failed_at"] = failed["step"]
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Dobot M1 Verbindungs- und Frame-Analyse")
    parser.add_argument("--uri", default=DOBOT_URI)
    parser.add_argument("--listen", type=float, default=1.0, help="Sekunden unaufgefordert zuhören")
    args = parser.parse_args()

    log_path = ROOT / LOG_DIR / "probe.jsonl"
    logger = FrameLogger(log_path)
    report = asyncio.run(probe(args.uri, args.listen, logger))

    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\nFrame-Log: {log_path}")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

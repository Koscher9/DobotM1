"""Short, position-verified Z-axis jog using the classic M1 CMD 73 interface."""

from __future__ import annotations

import argparse
import asyncio
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import DOBOT_URI
from dobot.client import DobotClient, DobotError
from dobot.logger import FrameLogger
from dobot.protocol import jog_command, nonzero_alarm_bytes


def require_clear_alarm_bytes(alarms: bytes | None) -> None:
    if alarms is None or len(alarms) != 32:
        raise DobotError("CMD-20-Alarmstatus unbekannt; Jog wird abgebrochen.")
    if any(alarms):
        raise DobotError(
            "CMD-20 enthält nicht-null Alarm-Rohbytes "
            f"({nonzero_alarm_bytes(alarms)}); Jog wird abgebrochen. "
            "Alarmursache am Controller klären und nicht automatisch löschen."
        )


def jog_duration_ms(value: str) -> int:
    try:
        duration = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Dauer muss eine Zahl in Millisekunden sein") from exc
    if not math.isfinite(duration) or not 50 <= duration <= 250:
        raise argparse.ArgumentTypeError("Dauer muss zwischen 50 und 250 ms liegen")
    return round(duration)


async def run(uri: str, duration_ms: int, positive: bool) -> None:
    logger = FrameLogger(ROOT / "logs" / "direct_z.jsonl")
    client = DobotClient(uri=uri, logger=logger)
    alarms_before: bytes | None = None
    try:
        await client.connect()
        await client.set_jog_ratios(10.0, 10.0)
        start_pose = await client.get_pose()
        start_alarms = await client.get_alarms()
        alarms_before = start_alarms
        print(f"CMD-20 Alarmbytes vor dem Jog: {nonzero_alarm_bytes(start_alarms)}")
        require_clear_alarm_bytes(start_alarms)
        direction = "aufwärts" if positive else "abwärts"
        jog_cmd = jog_command(axis_index=2, positive=positive)
        print(
            f"Sende J3-Jog {direction}: CMD 73, isJoint=1, "
            f"jogCmd={jog_cmd}, {duration_ms} ms, 10 %."
        )
        try:
            await client.jog(is_joint=True, axis_index=2, positive=positive)
            await asyncio.sleep(duration_ms / 1000)
        finally:
            await client.stop_jog()

        await asyncio.sleep(0.1)
        end_pose = await client.get_pose()
        end_alarms = await client.get_alarms()
        delta_z = end_pose.z - start_pose.z
        delta_j3 = end_pose.j3 - start_pose.j3
        print(f"Z vorher/nachher: {start_pose.z:.3f} -> {end_pose.z:.3f} mm (Δ {delta_z:+.3f})")
        print(f"J3 vorher/nachher: {start_pose.j3:.3f} -> {end_pose.j3:.3f} (Δ {delta_j3:+.3f})")
        print(f"CMD-20 Alarmbytes danach: {nonzero_alarm_bytes(end_alarms)}")
        if end_alarms != start_alarms:
            raise DobotError(
                "CMD-20 Alarmdaten haben sich während des Tests geändert; "
                "nicht erneut joggen und Controllerstatus prüfen."
            )
        if abs(delta_j3) < 0.01:
            raise DobotError(
                "Keine messbare J3-Bewegung: Jog nicht wiederholen; Diagnose-Log prüfen."
            )
        if (delta_j3 > 0) != positive:
            raise DobotError(
                "J3 bewegte sich entgegen der angeforderten Richtung; Jog nicht wiederholen."
            )
        print("Bewegung abgeschlossen; Richtung durch Poseänderung bestätigt.")
        print(f"Diagnose-Log: {logger.path}")
    except DobotError as exc:
        print(f"Fehler: {exc}")
        if alarms_before is not None:
            print(f"CMD-20 Alarmbytes vor dem Jog: {nonzero_alarm_bytes(alarms_before)}")
        print(f"Diagnose-Log: {logger.path}")
        raise SystemExit(1)
    finally:
        await client.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Kurzer, positionsgeprüfter Z-Jog mit der klassischen M1-Schnittstelle"
    )
    parser.add_argument("--uri", default=DOBOT_URI, help="WebSocket-URI")
    parser.add_argument("direction", choices=("up", "down"), help="J3-Richtung")
    parser.add_argument(
        "--ms",
        dest="duration_ms",
        type=jog_duration_ms,
        required=True,
        help="Jog-Dauer in Millisekunden (50–250)",
    )
    args = parser.parse_args()
    asyncio.run(run(args.uri, args.duration_ms, args.direction == "up"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

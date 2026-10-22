"""Tkinter hold-to-jog panel for the Dobot M1."""

from __future__ import annotations

import tkinter as tk
from concurrent.futures import Future
from pathlib import Path
from tkinter import ttk

from config import DOBOT_URI, JOG_ACCEL_RATIO, JOG_VELOCITY_RATIO, LOG_DIR, POSE_POLL_MS
from dobot.client import DobotError, DobotThread
from dobot.logger import FrameLogger
from dobot.protocol import CARTESIAN_AXES, JOINT_AXES, describe_alarm_byte8

ROOT = Path(__file__).resolve().parents[1]


class JogApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Dobot M1 — manuelle Achsensteuerung")
        self.geometry("720x560")
        self.minsize(640, 500)

        log_path = ROOT / LOG_DIR / "jog.jsonl"
        self.robot = DobotThread(uri=DOBOT_URI, logger=FrameLogger(log_path))
        self.robot.start()

        self._connected = False
        self._jogging = False
        self._poll_after: str | None = None

        self.uri_var = tk.StringVar(value=DOBOT_URI)
        self.status_var = tk.StringVar(value="Getrennt")
        self.alarm_var = tk.StringVar(value="Alarm: —")
        self.mode_var = tk.StringVar(value="joint")
        self.ratio_var = tk.DoubleVar(value=JOG_VELOCITY_RATIO)
        self.pose_vars = {
            name: tk.StringVar(value="—")
            for name in (*CARTESIAN_AXES, *JOINT_AXES)
        }

        self._build()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build(self) -> None:
        pad = {"padx": 8, "pady": 6}

        top = ttk.Frame(self)
        top.pack(fill=tk.X, **pad)
        ttk.Label(top, text="URI").pack(side=tk.LEFT)
        ttk.Entry(top, textvariable=self.uri_var, width=32).pack(side=tk.LEFT, padx=6)
        ttk.Button(top, text="Verbinden", command=self._connect).pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="Trennen", command=self._disconnect).pack(side=tk.LEFT)
        ttk.Label(top, textvariable=self.status_var).pack(side=tk.RIGHT)

        actions = ttk.Frame(self)
        actions.pack(fill=tk.X, **pad)
        ttk.Button(actions, text="NOT-HALT", command=self._e_stop).pack(side=tk.LEFT)
        ttk.Button(actions, text="Alarme löschen", command=self._clear_alarms).pack(side=tk.LEFT, padx=8)
        ttk.Label(actions, textvariable=self.alarm_var).pack(side=tk.LEFT, padx=12)

        modes = ttk.Frame(self)
        modes.pack(fill=tk.X, **pad)
        ttk.Label(modes, text="Raum").pack(side=tk.LEFT)
        ttk.Radiobutton(modes, text="Gelenke (J1–J4)", value="joint", variable=self.mode_var).pack(side=tk.LEFT, padx=6)
        ttk.Radiobutton(modes, text="Kartesisch (X Y Z R)", value="cart", variable=self.mode_var).pack(side=tk.LEFT)

        speed = ttk.Frame(self)
        speed.pack(fill=tk.X, **pad)
        ttk.Label(speed, text="Jog-Ratio %").pack(side=tk.LEFT)
        ttk.Scale(
            speed,
            from_=5,
            to=80,
            orient=tk.HORIZONTAL,
            variable=self.ratio_var,
            command=self._on_ratio,
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)
        self.ratio_label = ttk.Label(speed, text=f"{int(JOG_VELOCITY_RATIO)}")
        self.ratio_label.pack(side=tk.LEFT)

        pose = ttk.LabelFrame(self, text="Pose")
        pose.pack(fill=tk.X, **pad)
        for col, name in enumerate(CARTESIAN_AXES):
            ttk.Label(pose, text=name).grid(row=0, column=col, padx=10, pady=2)
            ttk.Label(pose, textvariable=self.pose_vars[name], width=10).grid(row=1, column=col)
        for col, name in enumerate(JOINT_AXES):
            ttk.Label(pose, text=name).grid(row=2, column=col, padx=10, pady=2)
            ttk.Label(pose, textvariable=self.pose_vars[name], width=10).grid(row=3, column=col)

        joints = ttk.LabelFrame(self, text="Achsen — Taste halten zum Fahren, loslassen zum Stoppen")
        joints.pack(fill=tk.BOTH, expand=True, **pad)

        joint_specs = [
            ("J1 / X  Basis", 0),
            ("J2 / Y  Arm", 1),
            ("J3 / Z  Hub", 2),
            ("J4 / R  Rotation", 3),
        ]
        for row, (label, index) in enumerate(joint_specs):
            ttk.Label(joints, text=label).grid(row=row, column=0, sticky=tk.W, padx=8, pady=8)
            minus = ttk.Button(joints, text="−")
            plus = ttk.Button(joints, text="+")
            minus.grid(row=row, column=1, padx=8, ipadx=16, ipady=8)
            plus.grid(row=row, column=2, padx=8, ipadx=16, ipady=8)
            self._bind_hold(minus, index, False)
            self._bind_hold(plus, index, True)

        hint = ttk.Label(
            self,
            text="Arbeitsraum frei halten. Ratio zuerst niedrig lassen. Bei Problemen: py -3 tools/probe.py",
            wraplength=680,
        )
        hint.pack(fill=tk.X, padx=8, pady=(0, 8))

    def _bind_hold(self, button: ttk.Button, axis_index: int, positive: bool) -> None:
        button.bind("<ButtonPress-1>", lambda _e: self._jog_start(axis_index, positive))
        button.bind("<ButtonRelease-1>", lambda _e: self._jog_stop())

    def _connect(self) -> None:
        uri = self.uri_var.get().strip()
        self.robot.uri = uri
        self.robot.client.uri = uri
        self.status_var.set("Verbinde …")

        def done(fut: Future) -> None:
            err = fut.exception()
            self.after(0, lambda: self._on_connected(err))

        self.robot.on_done(self.robot.client.connect(), done)

    def _on_connected(self, err: BaseException | None) -> None:
        if err is not None:
            self._connected = False
            self.status_var.set(f"Fehler: {err}")
            return
        self._connected = True
        self.status_var.set("Verbunden")
        self._schedule_poll()

    def _disconnect(self) -> None:
        self._stop_poll()
        self._connected = False

        def done(fut: Future) -> None:
            self.after(0, lambda: self.status_var.set("Getrennt"))

        try:
            self.robot.on_done(self.robot.client.close(), done)
        except DobotError:
            self.status_var.set("Getrennt")

    def _e_stop(self) -> None:
        self._jogging = False
        try:
            self.robot.submit(self.robot.client.emergency_stop())
        except DobotError as exc:
            self.status_var.set(str(exc))
        else:
            self.status_var.set("Not-Halt gesendet")

    def _clear_alarms(self) -> None:
        try:
            self.robot.submit(self.robot.client.clear_alarms())
        except DobotError as exc:
            self.status_var.set(str(exc))

    def _on_ratio(self, _value: str) -> None:
        ratio = float(self.ratio_var.get())
        self.ratio_label.config(text=str(int(ratio)))
        if not self._connected:
            return
        try:
            self.robot.submit(self.robot.client.set_jog_ratios(ratio, JOG_ACCEL_RATIO))
        except DobotError:
            pass

    def _jog_start(self, axis_index: int, positive: bool) -> None:
        if not self._connected:
            self.status_var.set("Nicht verbunden")
            return
        is_joint = self.mode_var.get() == "joint"
        self._jogging = True

        def done(fut: Future) -> None:
            err = fut.exception()
            if err is not None:
                self.after(0, lambda: self.status_var.set(str(err)))

        try:
            self.robot.on_done(self.robot.client.jog(is_joint, axis_index, positive), done)
        except DobotError as exc:
            self.status_var.set(str(exc))

    def _jog_stop(self) -> None:
        self._jogging = False
        if not self._connected:
            return
        try:
            self.robot.submit(self.robot.client.stop_jog())
        except DobotError:
            pass

    def _schedule_poll(self) -> None:
        self._stop_poll()
        self._poll()

    def _stop_poll(self) -> None:
        if self._poll_after is not None:
            self.after_cancel(self._poll_after)
            self._poll_after = None

    def _poll(self) -> None:
        if not self._connected:
            return

        def pose_done(fut: Future) -> None:
            err = fut.exception()
            if err is not None:
                self.after(0, lambda: self.status_var.set(str(err)))
                return
            pose = fut.result()
            self.after(0, lambda: self._apply_pose(pose))

        def alarm_done(fut: Future) -> None:
            if fut.exception() is not None:
                return
            alarms = fut.result()
            byte8 = alarms[8] if len(alarms) > 8 else 0
            self.after(0, lambda: self.alarm_var.set(f"Alarm: {describe_alarm_byte8(byte8)}"))

        try:
            self.robot.on_done(self.robot.client.get_pose(), pose_done)
            self.robot.on_done(self.robot.client.get_alarms(), alarm_done)
        except DobotError as exc:
            self.status_var.set(str(exc))
            self._connected = False
            return
        self._poll_after = self.after(POSE_POLL_MS, self._poll)

    def _apply_pose(self, pose) -> None:
        values = pose.as_dict()
        for name, value in values.items():
            self.pose_vars[name].set(f"{value:8.2f}")

    def _on_close(self) -> None:
        self._stop_poll()
        try:
            self.robot.stop()
        except Exception:
            pass
        self.destroy()


def main() -> None:
    app = JogApp()
    app.mainloop()


if __name__ == "__main__":
    main()

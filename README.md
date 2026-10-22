# Dobot M1 — manuelle Achsensteuerung

Lokales Python-Projekt für den Dobot M1 (SCARA) im Labornetz. Erster Stand: WebSocket-Client, Tkinter-Jog-Oberfläche und ein Diagnose-Tool.

Standard-Adresse:

```
ws://192.168.0.97:54321
```

## Sicherheit

- Arbeitsraum frei halten, bevor eine Achse bewegt wird.
- Jog-Ratio startet niedrig (25 %). Erst erhöhen, wenn die Richtung stimmt.
- Tasten sind **halten zum Fahren** — Loslassen sendet Stopp.
- **NOT-HALT** stoppt den Jog und leert die Befehlsqueue.
- Der untere Z-Endschalter (Alarm-Byte 8 = `0x20`) blockiert Abwärtsfahrt.

## Setup

Python 3.10+ empfohlen. Unter Windows oft `py -3` statt `python`. Im Projektordner:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

PC und Roboter müssen im gleichen Netz liegen. Die URI steht in `config.py`.

## Jog-Oberfläche

```powershell
py -3 jog.py
```

Funktionen:

- Verbinden / Trennen
- Gelenke J1–J4 oder kartesisch X/Y/Z/R
- Plus/Minus halten
- Live-Pose und Alarm-Byte 8
- Alarme löschen

Frames der UI landen in `logs/jog.jsonl` (nicht im Git).

## Diagnose, wenn nichts geht

```powershell
py -3 tools/probe.py
```

Das Skript prüft nacheinander:

1. TCP zu `192.168.0.97:54321`
2. WebSocket-Handshake
3. unaufgeforderte Frames
4. CMD 10 (Pose)
5. CMD 20 (Alarme)

Ergebnis kommt als JSON auf die Konsole, Rohframes nach `logs/probe.jsonl`.

## Bekannte Firmware-Falle

Nach Cold Boot kann J3 intern bei `0.00 mm` stehen. Dann fährt Z in Mode 1 nach oben, nach unten aber still — ohne Alarm. Mode-4-Direktsteuerung ist bewusst noch nicht in dieser Version; zuerst Mode-1-JOG und Probe-Log auswerten.

## Projektstruktur

```
config.py          URI und Jog-Ratio
dobot/protocol.py  Binärframes
dobot/client.py    WebSocket + Hintergrund-Thread
dobot/logger.py    JSONL-Frames
ui/jog_app.py      Tkinter
tools/probe.py     Analyse
jog.py             Start der Oberfläche
```

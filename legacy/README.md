# Dobot M1 — manuelle Achsensteuerung

Lokales Python-Projekt für den Dobot M1 (SCARA) im Labornetz. Erster Stand: WebSocket-Client, Tkinter-Jog-Oberfläche und ein Diagnose-Tool.

Standard-Adresse (an die Anlage angepasst):

```
ws://192.168.50.150:54321
```

## Sicherheit

- Arbeitsraum frei halten, bevor eine Achse bewegt wird.
- Jog-Ratio startet niedrig (10 %). Erst erhöhen, wenn alle Richtungen geprüft sind.
- Tasten sind **halten zum Fahren** — Loslassen sendet Stopp.
- **NOT-HALT** stoppt den Jog und leert die Befehlsqueue.
- CMD-20-Alarme werden als Rohbytes angezeigt. Ihre frühere Zuordnung zu einem einzelnen Z-Endschalter war nicht verlässlich.
- Ein fehlgeschlagener oder zu kurzer CMD-20-Read wird als **unbekannt** angezeigt, nicht als Nullalarme. Jog-Befehle sind gesperrt, solange keine vollständige CMD-20-Antwort mit ausschließlich Nullbytes vorliegt; bei nicht-null Bytes bleibt die Ursache ungeklärt und muss am Controller geprüft werden. Auch Nullbytes allein sind keine Sicherheitsfreigabe.
- Alarme beim Verbinden nicht automatisch löschen. **Alarme löschen** nur verwenden, wenn Ursache und Zustand bekannt sind.

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
- Live-Pose und nicht-null CMD-20-Alarmbytes
- Alarme löschen

Frames der UI landen in `logs/jog.jsonl` (nicht im Git).

## Kurzer Z-Test mit CMD 73

Der klassische M1-Jog-Befehl ist CMD 73 (Gelenk-Jog: J3+ = 5, J3− = 6). Das Diagnosewerkzeug sendet diesen nativen Jog-Befehl kurz, stoppt anschließend und vergleicht die Pose:

Nur bei freiem Arbeitsraum, geklärtem Controllerstatus und direkter Beobachtung ausführen. Die Jog-Dauer ist auf 50–250 ms begrenzt und die Geschwindigkeit auf 10 %. Bei unbekanntem oder nicht-null CMD-20-Rohstatus bricht das Tool vor dem Jog ab. Führe die Befehle einzeln in PowerShell im Projektordner aus:

```powershell
# 1. Kurzer Aufwärtstest
py -3 .\tools\direct_z.py up --ms 100

# 2. Nur wenn oben eine sichtbare Bewegung und ein passendes positives ΔJ3 gemeldet wurde:
py -3 .\tools\direct_z.py down --ms 100
```

`up`/`down` sind Richtungen; `--ms` braucht immer eine Dauer, zum Beispiel `100`. Alte Schreibweisen wie `--down 0.5`, `--down-ms` ohne Zahl oder `--down-250` funktionieren nicht. Ein erfolgreicher Aufruf muss „Bewegung abgeschlossen“ sowie Vorher-/Nachher-Pose ausgeben. Bei „Keine messbare J3-Bewegung“ den Abwärtstest nicht starten und den Inhalt von `logs\direct_z.jsonl` sichern.

Die GUI startest du separat:

```powershell
py -3 .\jog.py
```

Das Terminal meldet den Start; im Fenster auf **Verbinden** klicken, **Gelenke (J1–J4)** wählen und zum Joggen die jeweilige Taste kurz gedrückt halten. Loslassen stoppt. Erscheint kein Fenster oder kehrt PowerShell sofort zur Eingabe zurück, ist die GUI nicht gestartet — dann die komplette Fehlermeldung aus dem Terminal sichern.

Die Anwendung ordnet CMD-20-Rohdaten keinem einzelnen Alarm oder Endschalter zu und löscht Alarme nicht automatisch. Jog-Befehle werden bereits im Client abgelehnt, wenn der Alarmstatus unbekannt ist oder irgendein Alarm-Rohbyte nicht null ist. Der Diagnose-Kurztest sendet CMD 73 nur, wenn eine vollständige CMD-20-Antwort aus 32 Nullbytes vorliegt; ein Nullstatus ist trotzdem keine Anlagenfreigabe. Nicht-null Rohdaten brechen den Test ab, bis die Ursache am Controller geklärt ist. Nach jedem tatsächlich gestarteten Test werden Pose, rohe Alarmbytes und Frames in `logs/direct_z.jsonl` protokolliert. Wenn keine messbare Bewegung erfolgt, nicht blind wiederholen: zuerst Log und Fehlerstatus auswerten. Den Arm nicht mit Kraft von Hand bewegen; Motoren/Bremse können ihn festhalten.

**Protokollreferenz:** Das öffentliche [HarvestX/dobot_m1](https://github.com/HarvestX/dobot_m1) definiert den nativen J3−-Jog als CMD 73, Wert 6. Dessen Alarmcode-Enum und `AlarmStateToCode`-Implementierung legen für das erste nicht-null Byte `[8]=0x25` den Kandidaten `0x46` (`ERR_LIMIT_AXIS4_POS`) nahe. Das ist ein Hinweis, keine bestätigte Diagnose: Die Zuordnung ist für die konkrete Steuerungs-/Firmwareversion nicht unabhängig verifiziert und erklärt die übrigen gesetzten Rohdaten nicht. Daher zeigt die Anwendung weiterhin Rohbytes, sperrt Jog bei nicht-null Werten und fordert den Abgleich mit der Controlleranzeige. Sie löscht nichts automatisch. Das 4-Achs-PDF und [TCP-IP-4Axis-Python](https://github.com/Dobot-Arm/TCP-IP-4Axis-Python) betreffen eine andere ASCII/TCP-Schnittstelle und ersetzen den klassischen M1-WebSocket-Treiber nicht.

## Diagnose, wenn nichts geht

```powershell
py -3 tools/probe.py
```

Das Skript prüft nacheinander:

1. TCP zu `192.168.50.150:54321`
2. WebSocket-Handshake
3. unaufgeforderte Frames
4. CMD 10 (Pose)
5. CMD 20 (Alarme)

Ergebnis kommt als JSON auf die Konsole, Rohframes nach `logs/probe.jsonl`. Ein strukturell ungueltiger oder zu kurzer Pose-/Alarm-Frame gilt als fehlgeschlagen. `motion_clearance` bleibt auch bei Nullbytes `unknown`: Die Probe ist kein Bewegungsfreigabe- oder Sicherheitscheck.

## CMD-20-Timeout in der Jog-Oberfläche

Im bisherigen Frame-Log gibt es WebSocket-Nachrichten mit zwei direkt aneinandergehängten Antworten (CMD 10 Pose + CMD 20 Alarme, insgesamt 76 Byte). Die alte Empfangsroutine erwartete pro Nachricht exakt einen Frame und verwarf deshalb beide Antworten; parallel gestartete, überlappende Polls konnten zusätzlich zu irreführenden Timeouts führen. Die aktuelle Routine zerlegt Nachrichten in einzelne Frames, stellt Pose-/Alarm-Polls nacheinander und serialisiert gleichzeitige Anfragen derselben CMD-ID. Ein `CMD 20`-Timeout bedeutet daher nicht mehr, dass der Roboter generell unerreichbar ist; `tools/probe.py` bestätigt bereits eine gültige Antwort mit Alarmbyte `0x25`.

CMD 20 wird beim aktuellen Probe erfolgreich beantwortet. Seine 32 Bytes werden jetzt unverändert protokolliert und nicht mehr als einzelne Achsen- oder Stallflags missdeutet. Der Z-Test verwendet den dokumentierten nativen CMD-73-Jog, prüft die tatsächliche Poseänderung und stoppt den Jog automatisch nach kurzer Dauer.

## Projektstruktur

```
config.py          URI und Jog-Ratio
dobot/protocol.py  Binärframes
dobot/client.py    WebSocket + Hintergrund-Thread
dobot/logger.py    JSONL-Frames
ui/jog_app.py      Tkinter
tools/probe.py     Analyse
tools/direct_z.py  kontrollierter Z-Test
jog.py             Start der Oberfläche
```

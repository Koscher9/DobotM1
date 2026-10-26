# Dobot M1: Diagnosekern

Umsetzung unseres Entwicklungsplans für den ursprünglichen Dobot M1: **M0 und lesende Diagnose in M1**. Die normale Diagnose liest Position und rohe Alarmdaten; `identify` liest zusätzlich Gerätekennung, Betriebsmodus und Firmwareversionen. Das Paket besitzt keine Bewegungs-, Homing-, Parameter- oder Alarmlöschfunktion. Erste reale Leseversuche sind in `docs/hardware-checks.md` dokumentiert; Betriebsbereitschaft und Referenzzustand sind weiterhin ungeklärt.

## Installation unter Windows

Voraussetzung: Python 3.12. Alle Befehle im Projektordner ausführen. Eine Aktivierung der Umgebung ist nicht erforderlich.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install .
```

Die Laufzeitabhängigkeit ist auf `websockets==17.3` festgelegt. Unter Linux sind dieselben Schritte mit `python3.12` und `.venv/bin/python` möglich. Version 0.2.0 wird auf Python 3.12 entwickelt und geprüft.

## Zuerst ohne Roboter ausprobieren

```powershell
.\.venv\Scripts\python.exe -m dobot_m1 demo
```

Die Demo verwendet eindeutig gekennzeichnete künstliche Antworten. Sie öffnet keinen Netzwerkzugang. In `diagnostics/` entstehen je Lauf drei Dateien mit einer eindeutigen Kennung: vollständige Nachrichten als `.jsonl`, Bericht als `.json` und beides zusammen als `.zip`.

Eine Aufzeichnung wird ausschließlich offline wiedergegeben:

```powershell
.\.venv\Scripts\python.exe -m dobot_m1 replay .\diagnostics\DEINE_KENNUNG.jsonl
```

Den Platzhalter durch die tatsächlich erzeugte JSONL-Datei ersetzen. Replay prüft die Befehlsreihenfolge und sendet niemals aufgezeichnete Frames an den Roboter. Es ist ein Kommunikationsnachweis anhand aufgezeichneter Nachrichten, keine Physiksimulation und keine Prüfung realer Bewegungen. Ein Bericht mit `ok: true` bestätigt ausschließlich die erfolgreich ausgewertete Diagnose. Auch 32 Nullalarmbytes ergeben keine Bewegungsfreigabe.

## Späterer lesender Gerätetest

Der verfügbare Gerätezugang und die tatsächliche URI müssen bekannt sein. Andere Programme, die den Roboter steuern, schließen. Ein früher gestartetes Jog-Programm wird von dieser Diagnose nicht angehalten. Die ersten ausgeführten Versuche und ihre Grenzen stehen in `docs/hardware-checks.md`.

`profiles/m1.example.toml` nach `profiles/m1.local.toml` kopieren und dort die tatsächlich verwendete WebSocket-URI eintragen. Beispielprofile bestätigen weder Geräteidentität noch Firmware oder Grenzwerte.

```powershell
.\.venv\Scripts\python.exe -m dobot_m1 diagnose --profile .\profiles\m1.local.toml
```

Alternativ ist eine ausdrücklich angegebene `--uri` möglich. Es gibt keinen voreingestellten Live-Endpunkt. `diagnose` liest zuerst CMD 10 und danach unabhängig davon CMD 20. Es verändert keinen Modus, keine Parameter, keine Queue und keine Alarme. Auch das normale Beenden sendet keinen Dobot-Schreibbefehl.

Optional: `--samples 10 --interval 0.25`. Nach dem ersten fehlgeschlagenen Diagnosezyklus wird die Aufnahme beendet und exportiert. Ein Timeout gilt nicht als Nachweis einer nicht unterstützten Funktion. Die betroffene Anfrage wird in derselben Sitzung nicht wiederholt, damit verspätete Antworten nicht als neue Antworten ausgegeben werden.

## Gerätekennung und Firmware zusätzlich auslesen

```powershell
.\.venv\Scripts\python.exe -m dobot_m1 identify --profile .\profiles\m1.local.toml
```

Dieser bewusst gewählte zusätzliche Lesetest erfasst zunächst Position und Alarme, danach Seriennummer, Name, aktuellen Modus und die acht Versions-Untertypen. Er schaltet keinen Modus um. Die Versionsabfragen entsprechen dem `getVersion(index)`-Aufruf auf der geprüften M1-Webseite. Eine Antwort muss zum angefragten Untertyp passen. Nach einem Versions-Timeout wird keine weitere Anfrage derselben ID gesendet.

Auch Identifikationsaufzeichnungen lassen sich mit `replay` offline wiedergeben. Gerätekennungen und echte Logs bleiben lokal; sie nicht ungeprüft in ein öffentliches Repository übernehmen. A9-Version und Angaben zum physischen Aufbau werden separat dokumentiert, nicht aus der Betriebsart geraten.

## Tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -t . -v
```

Alle neuen Tests arbeiten mit künstlichen Transporten oder einem simulierten WebSocket-Objekt. Sie benötigen keinen Roboter und öffnen keine echte Roboterverbindung.

Die unveränderten bisherigen Tests lassen sich separat als Vergleich ausführen:

```powershell
Push-Location legacy
..\.venv\Scripts\python.exe -m unittest discover -s tests -v
Pop-Location
```

## Struktur

- `models.py`: Einheiten, unveränderliche Beobachtungen, Statusalter und Alarmrohwerte.
- `protocol.py`: reines Binärformat und ausschließlich die beiden geprüften Leseanfragen.
- `transports/websocket.py`: Verbindung ohne Roboterinitialisierung.
- `session.py`: einziger Empfänger, Antwortprüfung, Timeouts und Sitzungswechsel.
- `controller.py`: unabhängige Erfassung von Position und Alarmen.
- `diagnostics.py` und `replay.py`: vollständige lokale Aufzeichnung, Export und Offline-Wiedergabe.
- `cli.py`: Diagnose, Demo und Replay. Eine GUI folgt in einer späteren Etappe.

Die bisherigen Dateien liegen unverändert unter `legacy/`, einschließlich ihrer eigenen README und Tests. Sie sind ein Vergleichsstand und kein Teil des neuen installierten Pakets. Dort vorhandene Bewegungsfunktionen wurden nicht neu getestet oder freigegeben; sie nicht parallel zur neuen Diagnose starten.

## Grenzen und nächster Schritt

- `diagnose` fragt keine Gerätekennung ab und meldet `identity: not_queried`; `identify` liest die nun belegten Getter. Fehlende oder unpassende Antworten bleiben Fehler oder unbekannte Angaben. Ein Firmwarestand allein bestätigt keine funktionierenden Schalter oder korrekten Bezugspunkte.
- Der Alarmdecoder erfindet keine Endschalterdeutung. Alle 32 Bytes bleiben erhalten.
- Datenalter ist das Alter des Empfangs, nicht ein vom Controller bestätigter Messzeitpunkt.
- Die Empfangsgrenze beträgt 64 KiB pro WebSocket-Nachricht. Eine JSONL-Aufzeichnung ist auf 16 MiB begrenzt. Bei Erreichen der Grenze endet die Diagnose mit einem Fehler; vorhandene Daten werden nicht still gekürzt. Alte Sitzungen werden nicht automatisch gelöscht.
- Bei einem mehrdeutigen oder ausstehenden Telegramm wird auf einen expliziten neuen Verbindungsaufbau verwiesen, nicht automatisch neu verbunden.
- Bei Strg+C wird die Verbindung bestmöglich geschlossen; die bereits geschriebenen JSONL-Daten bleiben erhalten. Ein regulärer Bericht/ZIP ist bei Prozessabbruch nicht garantiert.

Nächster Schritt: **die Zustandsauffälligkeiten und den physischen Not-Halt-Anschluss klären**. Es gibt noch keine Bewegungsfreigabe. M2 kann softwareseitig vorbereitet werden; M3 benötigt zusätzlich die geklärte Wiederinbetriebnahme. Siehe `docs/progress.md`, `docs/plan.md` und `docs/hardware-checks.md`.

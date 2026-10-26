# Dobot M1: Diagnosekern

Erste Umsetzung unseres Entwicklungsplans: **M0 und Offline-Softwareteil von M1** für den ursprünglichen Dobot M1. Das neue Paket liest ausschließlich Position und rohe Alarmdaten. Es besitzt keine Bewegungs-, Homing-, Parameter- oder Alarmlöschfunktion. Der echte M1 wurde mit dieser Version noch nicht angesprochen.

## Installation unter Windows

Voraussetzung: Python 3.12. Alle Befehle im Projektordner ausführen. Eine Aktivierung der Umgebung ist nicht erforderlich.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install .
```

Die Laufzeitabhängigkeit ist auf `websockets==17.3` festgelegt. Unter Linux sind dieselben Schritte mit `python3.12` und `.venv/bin/python` möglich. Version 0.1.0 wird zunächst auf Python 3.12 entwickelt und geprüft.

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

Dieser Schritt wurde noch nicht ausgeführt. Der verfügbare Gerätezugang und die tatsächliche URI müssen zuvor bekannt sein. Andere Programme, die den Roboter steuern, schließen. Ein früher gestartetes Jog-Programm wird von dieser Diagnose nicht angehalten.

`profiles/m1.example.toml` nach `profiles/m1.local.toml` kopieren und dort die tatsächlich verwendete WebSocket-URI eintragen. Beispielprofile bestätigen weder Geräteidentität noch Firmware oder Grenzwerte.

```powershell
.\.venv\Scripts\python.exe -m dobot_m1 diagnose --profile .\profiles\m1.local.toml
```

Alternativ ist eine ausdrücklich angegebene `--uri` möglich. Es gibt keinen voreingestellten Live-Endpunkt. `diagnose` liest zuerst CMD 10 und danach unabhängig davon CMD 20. Es verändert keinen Modus, keine Parameter, keine Queue und keine Alarme. Auch das normale Beenden sendet keinen Dobot-Schreibbefehl.

Optional: `--samples 10 --interval 0.25`. Nach dem ersten fehlgeschlagenen Diagnosezyklus wird die Aufnahme beendet und exportiert. Ein Timeout gilt nicht als Nachweis einer nicht unterstützten Funktion. Die betroffene Anfrage wird in derselben Sitzung nicht wiederholt, damit verspätete Antworten nicht als neue Antworten ausgegeben werden.

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

- Identitäts-, Firmware- und weitere Statusabfragen sind noch nicht für dein Gerät verifiziert und werden deshalb nicht geraten. Der Bericht zeigt ausdrücklich `identity: not_queried`.
- Der Alarmdecoder erfindet keine Endschalterdeutung. Alle 32 Bytes bleiben erhalten.
- Datenalter ist das Alter des Empfangs, nicht ein vom Controller bestätigter Messzeitpunkt.
- Die Empfangsgrenze beträgt 64 KiB pro WebSocket-Nachricht. Eine JSONL-Aufzeichnung ist auf 16 MiB begrenzt. Bei Erreichen der Grenze endet die Diagnose mit einem Fehler; vorhandene Daten werden nicht still gekürzt. Alte Sitzungen werden nicht automatisch gelöscht.
- Bei einem mehrdeutigen oder ausstehenden Telegramm wird auf einen expliziten neuen Verbindungsaufbau verwiesen, nicht automatisch neu verbunden.
- Bei Strg+C wird die Verbindung bestmöglich geschlossen; die bereits geschriebenen JSONL-Daten bleiben erhalten. Ein regulärer Bericht/ZIP ist bei Prozessabbruch nicht garantiert.

Nächster Schritt nach Prüfung dieses Softwarestands: **ein lesender Gerätetest mit vollständigem Diagnoseexport**. Erst danach folgen M2 und die Vorbereitung kontrollierter Jog-Versuche. Siehe `docs/progress.md`, `docs/plan.md` und `docs/hardware-checks.md`.

# Geräteprofil: derzeit unbekannte Eigenschaften

Zielmodell laut Besitzer: ursprünglicher Dobot M1. Die zusätzlich gelesene Kennung ist lokal gespeichert; sie wird nicht als allgemeiner Default ins Paket geschrieben.

- Tatsächliche WebSocket-URI: am vorhandenen Aufbau bestätigt, lokale Konfiguration.
- Seriennummer und Firmware: lokal gelesen; wesentliche Versionsangaben siehe `hardware-checks.md`.
- Zusätzliche Identitäts-/Versionsgetter: geprüft; weitere Status-/Sicherheitsfunktionen bleiben ungeklärt.
- Referenzierungs-, Antriebs- und Bremsenzustand: nicht geprüft.
- Achsgrenzen, Werkzeugversätze und I/O-Belegung: nicht bestätigt.

`profiles/m1.example.toml` enthält deshalb keine Live-URI und keine Bewegungsgrenzen. Lokale Profile werden von Git ausgeschlossen. Auch selbst eingetragene Werte gelten im Diagnosebericht nur als bereitgestellte Profildaten, nicht als vom Gerät verifiziert.

Die Bewegungsprobleme betreffen den Stand vom 22.10. Die neue lesende Software hat inzwischen echte Daten empfangen; der alte Jog-Stand wurde dabei nicht benutzt. M1Studio ist derzeit nicht verfügbar. Ein angeschlossener direkter Not-Halt fehlt laut Besitzer. Diese Angaben ersetzen keine Prüfung des physischen Aufbaus.

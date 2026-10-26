# Lokale Validierung

Geprüft am 26.10.2026 unter Windows mit Python 3.12.14 und websockets 17.3.

- Installierbares Wheel aus `pyproject.toml` gebaut und in einen getrennten Testordner installiert.
- Version 0.1.0: 37 neue Tests gegen das installierte Paket bestanden.
- Version 0.2.0: 47 Tests einschließlich Identitäts-/Firmwarematching und Replay der zusätzlichen Anfragen bestanden.
- Version 0.2.0: als Wheel gebaut, in der getrennten Testumgebung installiert und erneut mit allen 47 Tests geprüft.
- Ein echter `identify`-Lauf lieferte alle 13 passenden Leseantworten; die vollständige Aufzeichnung wurde anschließend erfolgreich offline wiedergegeben und ihr ZIP geprüft.
- 26 unveränderte Tests im verschobenen Vergleichsstand: bestanden.
- Installierter CLI-Aufruf `demo`: bestanden, ohne Live-Transport.
- Installierter CLI-Aufruf `replay` mit der erzeugten Aufzeichnung: bestanden.
- Enthaltene Demo-Daten im installierten Paket: vorhanden.
- Beide ZIP-Exporte: Inhalt und vollständige Frame-Datei geprüft.
- Die zwei ausgehenden Demo-Anfragen sind exakt CMD 10 und CMD 20, lesend, ohne Nutzlast.
- Alle 18 ursprünglichen Dateien unter `legacy/` werden gegen die Git-Blob-Prüfsummen des Ausgangsstands verifiziert.

Diese automatisierten Tests verwenden ausschließlich künstliche Antworten oder simulierte Verbindungsschnittstellen. Die davon getrennten realen Lesetests stehen in `hardware-checks.md`. Es gab keine Bewegungsversuche.

Die GitHub-Workflowdatei führt Installation, neue Tests, Demo und alte Tests auf Windows und Linux aus. Ihre tatsächlichen Läufe sind zusätzlich in GitHub zu prüfen; lokale Windows-Ergebnisse sind kein bereits bestandener Linux-Nachweis.

Bekannte Grenze: Gerätekennung und Firmware sind inzwischen gelesen, aber die Bedeutung sämtlicher Alarmbits, Messfrische, Referenzzustand und Bewegungsbereitschaft sind nicht bestätigt. Die Wiederinbetriebnahme und alle Bewegungsmeilensteine bleiben offen.

# Lokale Validierung

Geprüft am 26.10.2026 unter Windows mit Python 3.12.14 und websockets 17.3.

- Installierbares Wheel aus `pyproject.toml` gebaut und in einen getrennten Testordner installiert.
- 37 neue Tests gegen das installierte Paket: bestanden.
- 26 unveränderte Tests im verschobenen Vergleichsstand: bestanden.
- Installierter CLI-Aufruf `demo`: bestanden, ohne Live-Transport.
- Installierter CLI-Aufruf `replay` mit der erzeugten Aufzeichnung: bestanden.
- Enthaltene Demo-Daten im installierten Paket: vorhanden.
- Beide ZIP-Exporte: Inhalt und vollständige Frame-Datei geprüft.
- Die zwei ausgehenden Demo-Anfragen sind exakt CMD 10 und CMD 20, lesend, ohne Nutzlast.
- Alle 18 ursprünglichen Dateien unter `legacy/` werden gegen die Git-Blob-Prüfsummen des Ausgangsstands verifiziert.

Die Tests verwenden ausschließlich künstliche Antworten oder simulierte Verbindungsschnittstellen. Es wurde kein Roboter kontaktiert und kein Hardwaretest durchgeführt.

Die GitHub-Workflowdatei führt Installation, neue Tests, Demo und alte Tests auf Windows und Linux aus. Ihre tatsächlichen Läufe sind zusätzlich in GitHub zu prüfen; lokale Windows-Ergebnisse sind kein bereits bestandener Linux-Nachweis.

Bekannte Grenze: Ohne Geräteantworten sind Identität, Firmware, Bedeutung sämtlicher Alarmbits, Messfrische und Betriebszustand nicht bestätigt. M1 am Gerät und alle Bewegungsmeilensteine bleiben offen.

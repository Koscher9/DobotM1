# Geräteversuche

**Mit dem neuen Paket wurde bisher kein echter Geräteversuch ausgeführt.**

## Nächster Schritt: rein lesende Prüfung

1. Diesen Quellstand lokal installieren und zuerst `demo` offline prüfen.
2. Tatsächlich genutzte WebSocket-URI und Gerätezuordnung notieren. Andere Steuerprogramme schließen; sicherstellen, dass keine alte Bewegung läuft.
3. Einmal `diagnose --profile profiles/m1.local.toml` ausführen.
4. JSON-Bericht und ZIP mit vollständigen Frames sichern.
5. CMD-10-/CMD-20-Antwort, Länge, Prüfsumme, Einheiten und Alarmrohbytes auswerten. Eine fehlende Antwort führt zu Diagnose, nicht zu automatischem Moduswechsel oder Alarmlöschen.

Für jeden Versuch festhalten: Quellstand, Python-/Bibliotheksversion, Datum, Gerät und Firmware soweit bekannt, URI, erwartete Abfragen, erhaltene Antworten und Ergebnis. Noch keine Achse bewegen.

M1 ist erst nach Auswertung echter Antworten am Gerät bestätigt. Die Offline-Demo und Replay sind keine Hardwarefreigabe.

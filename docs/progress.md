# Fortschritt

Stand: 26.10.2026. Ausgangscommit: `7426c4a7621b4f9f936ad76a9bc84702ab92961a`.

## M0: Softwarebasis

- Bisherige 18 Dateien unverändert nach `legacy/` verschoben.
- Installierbares Paket und klar begrenzte Python-3.12-/WebSocket-Abhängigkeit angelegt.
- Gemeinsamer Plan und Protokollgrenzen dokumentiert.
- Neue Tests sowie separate alte Tests reproduzierbar ausführbar.

## M1: Offline-Softwareteil

- Reine Leseanfragen für Position und rohe Alarme.
- Kein versteckter Schreibzugriff beim Verbinden oder Schließen.
- Sitzungskennung, Gültigkeit und Empfangsalter.
- Mehrfachframes und begrenzte Nachrichtenrestverarbeitung.
- Antwortprüfung nach ID, Steuerbyte und Nutzdatenstruktur.
- Nach Timeout keine erneute Anfrage derselben ID ohne neue Sitzung.
- Alarmabfrage unabhängig vom Erfolg der Poseabfrage.
- Vollständige JSONL-Daten, Bericht, ZIP-Export und Offline-Demo/Replay.

## Noch nicht erledigt

Der **Hardwareteil von M1 ist ausstehend**. Keine echte Verbindung, Position, Alarmantwort oder Firmware wurde mit diesem Paket geprüft. M2 bis M5 sind nicht umgesetzt. Es gibt noch keine neue Jog-Steuerung oder Oberfläche.

Die erfolgreiche Offline-Demo kann weder Gerätebereitschaft noch Bremsen-, Referenzierungs- oder Bewegungsfunktionen bestätigen.

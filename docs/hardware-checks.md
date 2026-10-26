# Geräteversuche und offene Wiederinbetriebnahme

Stand: 26.10.2026. Vollständige Messdaten und Gerätekennungen bleiben lokal. Es wurden ausschließlich lesende Anfragen gesendet.

## Erster erfolgreicher Lesetest

Nach Umstellung des PC-Netzes auf das Gerätesubnetz antwortete der M1 auf drei Pose-/Alarmzyklen: sechs vollständige Antworten mit jeweils 32 Nutzdatenbytes und gültiger Prüfsumme. Die Aufzeichnung ließ sich offline wertgleich wiedergeben.

Die Rohwerte blieben stabil. Auffällig waren negatives Z/J3 und eine sehr große R/J4-Koordinate. Der Besitzer meldet die Hubachse gleichzeitig als ganz oben. Das ist ein ungeklärter Referenz-/Gerätezustand. Die Werte werden weder automatisch normalisiert noch durch einen Pose-Reset verdeckt.

Die 32 Alarmbytes sind nicht null. Decodervergleiche liefern mögliche Grenz-, Encoder- und Batteriemeldungen; die Zuordnung zur konkreten Firmware ist noch nicht vollständig bestätigt. Kein automatisches Alarmlöschen oder Teiletausch wurde daraus abgeleitet.

## Zusätzlich gelesene Geräteinformationen

Gezielte Getter lieferten Name und Seriennummer einer neueren M1-Serie. Bestätigt wurden:

- Aktueller Modus: Dobot Mode, Wert 1.
- Dobot-Firmware: 1.4.6.
- Driver1 bis Driver4: jeweils 1.4.5.
- 3D-Printing-Firmware: 1.1.3.
- EndEffector: 1.1.4.
- FPGA: 1.1.0.
- A9-Anzeige: 02007600, über den auf der A9-Seite verwendeten Versionsgetter separat gelesen.

Diese Angaben liegen über den in den untersuchten Handbuchabschnitten genannten Firmware-Mindestständen für die Referenzierfunktion. Das bestätigt weder funktionierende Schalter noch einen geeigneten Bewegungsablauf. Ein Firmware-Update ist aus diesen Angaben nicht als erster Reparaturschritt begründet.

## Tatsächliche Voraussetzungen für weitere Bewegung

Der Besitzer meldet: kein angeschlossener direkter Not-Halt-Taster, kein Werkzeug montiert. Das Herstellerhandbuch nennt einen angeschlossenen Not-Halt als Inbetriebnahmevoraussetzung. Eine Web- oder Python-Schaltfläche ersetzt diese physische Funktion nicht.

Die dokumentierte Referenzfahrt beginnt mit J3 zur oberen Referenzposition und setzt anschließend J1/J2 in Bewegung. Sie wurde nicht gestartet. Der Besitzer möchte die bereits oben stehende Hubachse nicht weiter nach oben fahren und die manuelle Steuerung selbst übernehmen.

Bewegungsversuche und automatische Referenzierung bleiben ausstehend. Zuerst Anschlussausführung, passenden Not-Halt und den vorgesehenen Wiederinbetriebnahmeweg klären. Keine vermuteten Kontakte brücken und keinen Modus-/Pose-Reset als Abkürzung verwenden.

## Weiterer Ablauf

1. Fotos von Rückseite/Anschlussfeld und Typenschild zur Zuordnung des physischen Aufbaus, ohne Gehäuseöffnung oder Armbewegung.
2. Passenden Not-Halt-Anschluss anhand der richtigen Herstellerunterlage zuordnen und fachgerecht herstellen/prüfen.
3. Encoder-/Batterie- und Referenzzustand anhand bestätigter Alarme und Geräteausführung klären.
4. Anschließend einen konkreten, vom Besitzer bedienten Bewegungsversuch vorbereiten. Keine pauschale Aufwärts- oder Abwärtsfreigabe aus den jetzigen Zahlen ableiten.

Quellen: [M1 User Guide V1.5.3](https://download.dobot.cc/product-manual/dobot-m1/en/pdf/Dobot-M1-User-Guide-V1.5.3.pdf), Abschnitte Inbetriebnahme und 7.3.1; geräteeigene Webquellen; lokal gespeicherte Leseantworten. Keine Bewegung wurde während der bisherigen Tests ausgeführt.

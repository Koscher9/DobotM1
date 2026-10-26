# Protokoll und Grenzen dieses Meilensteins

Ziel ist der ursprüngliche M1. Der Transport bleibt vorerst WebSocket entsprechend dem vorhandenen Projekt. Dokumentierte UDP-Ports sind keine austauschbaren WebSocket-Endpunkte.

## Erzeugte Dobot-Anfragen

- CMD 10 lesen, Steuerbyte 0, leere Nutzlast: `AA AA 02 0A 00 F6`.
- CMD 20 lesen, Steuerbyte 0, leere Nutzlast: `AA AA 02 14 00 EC`.

Im normalen `diagnose`-Ablauf werden weiterhin ausschließlich diese beiden Leseanfragen gesendet. `not_queried` bedeutet nicht `unsupported`.

## Zusätzlich verifizierte Identifikations-Getter ab 0.2.0

- CMD 0 lesen, leere Nutzlast: Seriennummer.
- CMD 1 lesen, leere Nutzlast: Gerätename.
- CMD 2 lesen, ein Datenbyte mit Untertyp 1 bis 8: Firmwareversion.
- CMD 161 lesen, leere Nutzlast: aktueller Modus. Dies ist ausdrücklich kein Modus-Schreibzugriff.

Die zusätzliche Abfrage erfolgt nur über den bewusst gewählten Befehl `identify`. Bei allen Anfragen bleiben Lese-/Schreibbit und Queuebit null. Beliebige Nutzdaten oder Schreibbefehle sind nicht erlaubt.

Die HTML-Quellen des untersuchten Roboters belegen `getVersion(index)` auf `/file/mindex/` und den Modusgetter mit leerer Nutzlast auf derselben Seite. Die Definitionen stehen in `/style/js/dobot/dobot_def.js`. Die Startseite interpretiert Posewerte mit denselben acht Little-Endian-Floats wie unser Programm. Es wurden nur Seitenquellen gelesen, keine Updates oder Bedienelemente ausgeführt.

Die Firmwareanfrage benötigt bei diesem Gerät den Untertyp als Parameter. Eine indexfreie Darstellung in einer älteren Protokolltabelle wird deshalb nicht ungeprüft übernommen. Antworten enthalten Untertyp und Version; bei fehlendem Revisionsbyte bleibt der Wert unbekannt statt künstlich null. Gleiche Befehls-ID bei unterschiedlichen Untertypen erfordert zusätzliches Matching und eine gemeinsame Timeout-Sperre.

Poseantwort: genau 32 Datenbytes, `<8f`; X/Y/Z/J3 in mm, R/J1/J2/J4 in Grad. Nicht endliche Werte werden abgelehnt. Erfolgreiche Dekodierung bestätigt noch keinen richtigen Referenzzustand.

Alarmantwort: genau 32 Datenbytes. Kurze Antworten werden nicht mit Nullen aufgefüllt. Rohdaten werden ohne erfundene Zuordnung zu Endschaltern gespeichert.

## Empfang und zeitliche Mehrdeutigkeit

Länge zählt ID, Steuerbyte und Parameter. Summe dieser Bytes plus Prüfsumme modulo 256 ist null. Eine Nachricht kann mehrere Frames enthalten. Ein unvollständiger plausibler Frame wird begrenzt gepuffert, nicht als gültige Antwort ausgegeben. Ein korruptes großes Längenfeld kann bis zum Anfrage-Timeout auf weitere Daten warten; danach wird der Restpuffer verworfen, sodass die folgende Alarmabfrage nicht durch diesen Rest blockiert bleibt.

Die Sitzung hat einen Empfänger und eine normale Anfrage gleichzeitig. Eine Schreibbestätigung erfüllt keine Leseanfrage. Nach Timeout oder Abbruch nach Versand wird dieselbe ID bis zur nächsten Sitzung nicht wiederholt. Späte Antworten dieser ID werden aufgezeichnet, nicht als gültiger aktueller Status übernommen.

Ohne vom Controller gelieferte Anfragekennung lassen sich unaufgeforderte und angeforderte formal identische Frames nicht in jedem Fall unterscheiden. Gültige unaufgeforderte Statusframes werden erfasst. Das Serververhalten und die tatsächliche Messfrische bleiben Teil der Geräteprüfung. Empfangszeit allein beweist keinen Sensorzeitpunkt.

## Bereits aus der Analyse bekannte spätere Arbeiten

CMD 161 nicht automatisch setzen; Modusannahme getrennt prüfen. Alarmlöschen nach dokumentiertem Format und mit eigener Aktion prüfen. Gelenk-/kartesische Parameter getrennt behandeln. Software-Stopp priorisieren und nicht als physischen Not-Halt darstellen. Diese Schreibfunktionen gehören nicht zu M1 und sind hier nicht implementiert.

Quellen: [M1-Protokoll V1.1](https://download.dobot.cc/development-protocol/dobot-m1/pdf/en/Dobot-M1-Communication-Protocol-V1.1.pdf), [V1.0](https://download.dobot.cc/development-protocol/dobot-m1/pdf/en/Dobot-M1-Communication-Protocol-V1.0.pdf), [Alarmbeschreibung](https://download.dobot.cc/development-protocol/dobot-m1/pdf/alarms/en/Dobot-M1-Alarm-Description.pdf), eigener Ausgangscommit und gemeinsame Repositoryanalyse. Dokumentvarianten und Widersprüche werden anhand echter Antworten geprüft; keine vollständige Kompatibilität ist behauptet.

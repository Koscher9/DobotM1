# Dobot M1: gemeinsamer Entwicklungsplan

Stand: 26.10.2026. Zielgerät: ursprünglicher Dobot M1, keine Pro-Variante.

## 1. Unsere Entscheidung

**Version 1 soll Diagnose und zuverlässiges manuelles Verfahren ermöglichen.** Diesen Umfang hast du ausdrücklich gewählt. Gespeicherte Punkte, automatische Abläufe und Greifersteuerung gehören zu späteren Ausbaustufen.

Wir behalten Python als Grundlage und beginnen auf Windows. Den bereits von dir benutzten WebSocket-Zugang untersuchen wir zuerst. Kommunikation, Gerätezustand und Oberfläche werden dabei getrennt aufgebaut. Eine funktionierende Verbindung wird nicht mit einer betriebsbereiten Steuerung gleichgesetzt.

Eine „perfekte“ Steuerung lässt sich nicht allein aus Dokumenten garantieren. Unser Ziel ist eine nachvollziehbare, testbare Software, deren Funktionen auf deinem Gerät schrittweise nachgewiesen werden. Dieses Dokument ist die Arbeitsgrundlage dafür; es implementiert oder aktiviert noch keine Robotersteuerung.

## 2. Welche Grundlagen zusammengeführt wurden

**Quelle A: Chat „Dobot M1 Software Recherche“.** Eingesehen wurden der Chat, der zugehörige ausführliche Rechercheverlauf, verfügbare Berichtsausschnitte und protokollierte Ergebnisse aus Herstellerunterlagen, SDKs und Communityprojekten. Die dort erzeugte 18-seitige PDF war in dieser lokalen Umgebung nicht als vollständige Datei verfügbar und wurde hier nicht erneut Seite für Seite geprüft. Wesentliche Community-Codebefunde wurden für diesen Abgleich zusätzlich direkt auf GitHub kontrolliert.

**Quelle B: unsere Repositoryanalyse.** Sie untersucht den heutigen Stand `7426c4a7621b4f9f936ad76a9bc84702ab92961a` sowie den Stand vom 22.10. `8aa03bc4c978722426c27cfff8659bd2b16937db`. Dazu gehören 26 bestandene vorhandene Tests und zusätzliche Simulationen konkreter Fehlerfälle. Details stehen in `DobotM1_Repositoryanalyse_2026-10-26.txt`.

**Deine bestätigten Erfahrungen:** Die Bewegungsprobleme stammen vom 22.10.; die heutige Überarbeitung wurde noch nicht am Roboter getestet. Die Verbindung gelang mit Python. M1Studio ist nicht installiert und lässt sich bei dir derzeit nicht installieren. Aktuelle Original-Alarmlogs fehlen.

Wir unterscheiden künftig konsequent:

- **Belegt:** im Quellcode, einer benannten Quelle oder einem reproduzierbaren Test nachweisbar.
- **Am Gerät bestätigt:** durch einen gespeicherten Versuch mit deinem M1 nachgewiesen.
- **Hypothese:** mögliche Erklärung, die noch überprüft werden muss.
- **Entscheidung:** eine bewusste Festlegung für unsere eigene Software.

Eine Simulation ist kein Geräteversuch. Eine Handbuchangabe ist kein Nachweis für jede Hardware-/Firmwarekombination.

## 3. Vergleich: Was wir übernehmen und was wir korrigieren

### 3.1 Der alte M1 besitzt nutzbare Entwicklungsgrundlagen

Die Recherche fand ein eigenes binäres M1-Protokoll, API-Unterlagen, SDK-Beispiele sowie Python-, Qt- und ROS-Projekte mit M1-Bezug. Unser Repository implementiert bereits wesentliche Teile dieses Binärformats.

**Folgerung:** Wir müssen weder Robotik-Grundfunktionen neu erfinden noch ein vollständiges Fremdframework übernehmen. Wir entwickeln einen kleinen eigenen Kern anhand überprüfter Referenzen. Fremdcode wird nur nach Lizenzprüfung übernommen.

### 3.2 WebSocket, UDP und seriell dürfen nicht vermischt werden

Die Recherche dokumentiert unter anderem UDP und seriellen Zugriff. Der vorhandene Python-Code benutzt dagegen `ws://192.168.50.150:54321`. Du hast bestätigt, dass eine Verbindung mit dem bisherigen Python-Programm gelang; vollständige Originaltelegramme liegen aktuell nicht vor.

**Entscheidung:** Der erste Adapter ist WebSocket. Die konfigurierte URI wird beim praktischen Start nochmals bestätigt. Sie ist eine Anlagenkonfiguration, kein hier bewiesener Herstellerstandard.

UDP-Portangaben aus alten und neueren Dokumenten dürfen nicht einfach in die WebSocket-URI eingesetzt werden. Gleiche Portnummern bedeuten keine gleichen Transportprotokolle. Ein zweiter Transport wird nur ergänzt, wenn ein konkretes Problem den Wechsel begründet. Automatische Gerätesuche und gleichzeitige Verbindungen über mehrere Wege entfallen in V1.

### 3.3 M1Studio ist hilfreich, aber keine Voraussetzung für den ersten Schritt

Die andere Recherche schlug einen erfolgreichen M1Studio-Versuch als Referenz vor. Bei dir ist das momentan keine nutzbare Voraussetzung.

**Anpassung:** Wir beginnen mit einer eigenen reinen Leseanwendung. Das Installationsproblem darf später separat untersucht werden. Es begründet weder einen Firmwarewechsel noch eine automatische Neukalibrierung.

### 3.4 Communitycode liefert Referenzen, keine fertige Steuerung

Der direkt nachgeprüfte ARCOR2-Code besitzt eine ausdrückliche M1-Klasse. Er verwendet aber auch feste Werkzeugversätze und I/O-Annahmen. Sein Basistreiber startet und leert beim Erzeugen einer Instanz die Queue, verändert Bewegungsparameter und kann Alarme löschen. Der Qt-Democode enthält ebenfalls automatische Schreibzugriffe sowie unbegrenzte Wiederholungsschleifen.

**Entscheidung:** Keine solche Bibliothek wird ungeprüft zur Live-Steuerung. Auslesen, Geräteeinstellungen ändern und Bewegung erhalten getrennte Aufrufe. Keine versteckten Schreibzugriffe in Konstruktoren oder `connect()`.

ROS/MoveIt, Hersteller-DLL und eine eigene TCP-Skriptbrücke bleiben mögliche spätere Alternativen. Sie sind für Diagnose und Jog in V1 keine notwendige Abhängigkeit. Die recherchierte Skriptbrücke ist ein selbst gestarteter Dienst, kein automatisch vorhandener M1-Pro-Endpunkt.

Falls später eine DLL erforderlich wird, müssen Header, Binärdatei, Architektur und Wrapper zusammenpassen. In der früheren Recherche wurde das offizielle Paket als 32-Bit und die untersuchten Communitydateien als 64-Bit erkannt. Auch gleich benannte Homing-Funktionen besitzen in den verglichenen Headern unterschiedliche Signaturen. Kein beliebiges Paket installieren und keine Funktionssignaturen zwischen Beispielen mischen.

### 3.5 Die alte Z-Sperre ist ein konkreter Fehlerkandidat

Im Stand vom 22.10. konnte eine ungesicherte Interpretation von Alarmbyte 8 die Z-Abwärtsfahrt vor dem Senden blockieren. Das ist im Code und mit einem künstlichen Wert nachweisbar. Es erklärt nicht automatisch fehlende Aufwärtsbewegung oder einseitige Armbewegungen.

**Entscheidung:** Rohdaten erhalten und alle Alarmbits anhand einer geprüften Zuordnung auswerten. Keine einzelne Rohbyte-Maske als angeblich sicheren Endschalter übernehmen. Nullbytes allein begründen ebenfalls keine vollständige Bewegungsbereitschaft.

### 3.6 Empfangs- und Statusfehler sind wichtiger als eine neue Oberfläche

Der alte Empfänger verarbeitete bei mehreren Antworten in einer WebSocket-Nachricht nur die erste. Die heutige Version verbessert das. Sie enthält aber unter anderem noch veraltete Alarmcaches, fehlende Schreibbestätigungen und eine fehleranfällige Antwortzuordnung.

**Entscheidung:** Die vorhandene Oberfläche dient als Referenz für Bedienabläufe. Ihre direkte Kopplung an den bisherigen Client wird nicht zum Architekturvorbild. Zuerst muss der Kommunikationskern die bekannten Fehlerfälle beherrschen.

### 3.7 Hardwarevarianten, Einheiten und Referenzierung brauchen ein Geräteprofil

Die Recherche weist auf unterschiedliche Hardware-/Firmwarestände, abweichende SDK-Funktionssignaturen und unterschiedliche veröffentlichte Achsgrenzen hin. Besonders Homing und J4-Grenzen dürfen nicht aus beliebigen Beispielen gemischt werden.

**Entscheidung:** Für dein Gerät führen wir ein nachvollziehbares Profil. Unbekannte Fähigkeiten bleiben ausdrücklich unbekannt. Keine geratenen Grenzwerte, Werkzeugversätze, I/O-Pegel oder automatisch ausgelösten Referenzfahrten.

J3 wird als lineare Achse behandelt. J1, J2 und J4 sind rotierende Achsen. Gelenkwerte und kartesische Koordinaten werden getrennt benannt. Gleiche XYZ-Ziele können unterschiedliche Armstellungen bedeuten.

## 4. Was Version 1 enthalten soll

### Diagnose

- URI und Verbindungszustand anzeigen; klare Fehler bei Zeitüberschreitung.
- Gerätekennung und Firmwareinformationen lesen, soweit die jeweilige Lesefunktion verifiziert und unterstützt ist.
- Pose und alle 32 Alarmbytes unverändert anzeigen und speichern.
- Datenalter, Verbindungssitzung und Gültigkeit sichtbar machen.
- Verfügbare Betriebsstatusdaten von unbestätigten Annahmen unterscheiden.
- Vollständige lokale Diagnosesitzung exportieren und offline wiedergeben können.

### Manuelles Verfahren

- Zuerst J1 bis J4 einzeln in beiden Richtungen, danach X/Y/Z/R.
- Gedrückthalten als bewusste Bedienhandlung; Loslassen fordert Stopp an.
- Kontrollierte Einstellungen für Geschwindigkeit und Beschleunigung mit Rückleseprüfung, soweit unterstützt.
- Software-Stopp mit nachvollziehbarem Versand-, Antwort- und Stillstandsstatus.
- Sperre mit verständlichem Grund, wenn Voraussetzungen fehlen.
- Kein automatisches Wiederanlaufen nach Trennen, Fehler oder Neustart.

Noch nicht Teil von V1: PTP-Zielfahrten, Punktverwaltung, Jobeditor, I/O-/Greifersteuerung, autonome Referenzierung, Internetfernsteuerung, Mehrroboterbetrieb und automatische Abläufe. Dafür werden keine vorsorglichen Großsysteme gebaut.

## 5. Technische Grundentscheidungen

### Python und Abhängigkeiten

Wir beginnen mit einer dokumentierten Python-3.12-Umgebung für Windows. Die vorherige Prüfung verwendete Python 3.12.14 mit websockets 17.3. Diese Kombination ist eine nachvollziehbare lokale Testbasis; die Bibliotheksversion auf deinem Roboter-PC wird beim Start erfasst.

Abhängigkeiten werden reproduzierbar festgehalten. Der Kern braucht zunächst wenig mehr als Standardbibliothek und WebSocket-Bibliothek. Die spätere lokale Oberfläche kann für V1 Tkinter verwenden, dessen Verfügbarkeit zu prüfen ist. Sie bleibt austauschbar. Eine aufwendigere Oberfläche ist kein Grund, vorher einen zweiten Steuerungskern aufzubauen.

### Ein Prozess und eine verantwortliche Robotersitzung

Genau eine Komponente besitzt die Verbindung und die Befehlsverwaltung. CLI und GUI senden fachliche Aufträge an diese Komponente. Sie erzeugen keine Telegramme und greifen nicht direkt auf den Transport zu.

Die Kommunikation läuft in einer asyncio-Ereignisschleife. Falls Tkinter benutzt wird, bleibt seine Hauptschleife im Hauptthread; ein Adapter überträgt Aufträge und unveränderliche Statusereignisse. UI-Elemente werden nur im GUI-Thread verändert. Ein zweites Programm darf nicht parallel als weiterer Steuerungsbesitzer verwendet werden; soweit technisch möglich erkennt unsere Anwendung eigene parallele Instanzen. Fremdprogramme kann sie nicht zuverlässig ausschließen.

### Protokoll und Transport trennen

Das Protokoll kennt Bytes, Befehlsformate und Antwortprüfung. Der Transport kennt ausschließlich Verbindung, Nachrichten und Versand. Die Sitzung ordnet Antworten zu. Der Controller entscheidet, welche fachliche Aktion in welchem Zustand zulässig ist.

Ein erster Treiber genügt. Die Trennung ermöglicht später UDP oder seriell, ohne bereits ungenutzte Adapter zu implementieren.

## 6. Vorgesehene Projektstruktur

Die folgende Struktur ist ein Zielbild. Dateien entstehen dann, wenn sie im jeweiligen Meilenstein gebraucht werden; keine leeren Frameworkschichten auf Vorrat.

- `pyproject.toml`: Paket, Pythonbasis und Entwicklungswerkzeuge.
- `README.md`: Installation, rein lesender Start, Diagnose und Grenzen.
- `profiles/m1.example.toml`: Beispiel ohne vorgetäuschte Gerätefreigabe. Lokale Anlagenwerte werden separat gespeichert.
- `docs/plan.md`: diese gemeinsame Arbeitsgrundlage.
- `docs/protocol-notes.md`: belegte Befehlsformate, Varianten und offene Widersprüche.
- `docs/device-profile.md`: konkrete Hardware-/Firmwaredaten und Herkunft bestätigter Einstellungen.
- `docs/hardware-checks.md`: tatsächlich ausgeführte Geräteversuche und Ergebnisse.
- `src/dobot_m1/models.py`: Pose, Einheiten, Alarmdaten, Zeitstempel und Auftragsstatus.
- `src/dobot_m1/protocol.py`: Packen, Zerlegen, Prüfsummen und Antwortschemata ohne Netzwerkzugriff.
- `src/dobot_m1/transports/websocket.py`: WebSocket-Verbindung ohne Moduswechsel oder Parameteränderung.
- `src/dobot_m1/session.py`: einziger Empfänger, Zuordnung, Zeitgrenzen, Sitzungskennung und Verbindungsabbau.
- `src/dobot_m1/controller.py`: öffentliche Diagnose-/Jog-/Stoppaktionen, Auftragsverwaltung und Bewegungszustand.
- `src/dobot_m1/readiness.py`: nachvollziehbare Softwarevoraussetzungen mit einzelnen Sperrgründen; keine Behauptung einer zertifizierten Sicherheitsfunktion.
- `src/dobot_m1/diagnostics.py`: vollständige Aufzeichnung und Export.
- `src/dobot_m1/replay.py`: Offline-Nachrichtenquelle für aufgezeichnete und künstliche Antworten; niemals zum Live-Senden von Bewegungsframes verwenden.
- `src/dobot_m1/cli.py`: erster Bedienweg für Diagnose und spätere bewusst gewählte Tests.
- `src/dobot_m1/ui/`: spätere Tkinter-Oberfläche und ihr Controlleradapter.
- `tests/unit/`: Protokoll, Einheiten, Statusentscheidungen.
- `tests/integration/`: künstlicher Transport, Zeitüberschreitungen, Verbindungswechsel und Ereignisfolgen.
- `tests/fixtures/`: synthetische und ausdrücklich gekennzeichnete echte Telegramme.

**Abhängigkeiten laufen von der Bedienung zum Controller, zur Sitzung und zum Transport.** Modelle und Protokoll werden von diesen Schichten genutzt und kennen keine GUI. Protokolltests brauchen weder Netzwerk noch Roboter.

Das bisherige Programm wird als gekennzeichneter Vergleichsstand bewahrt. Wiederverwendete Teile werden erst nach Prüfung und passenden Regressionstests in den neuen Kern übernommen. Kein gleichzeitiger Betrieb des alten Jog-Programms während neuer Gerätetests.

## 7. Datenmodell und Zustandsführung

### Geräteprofil

Enthalten sein sollen: Modell, Seriennummer soweit verfügbar, Hardware-/Firmwarestände, Transport und URI, unterstützte Lesefunktionen, nachgewiesene Parameterformate, bekannte Grenzwerte, Werkzeugprofil und Referenzierungsstatus. Jeder bestätigte Wert erhält Quelle oder Versuchsbezug. Fehlende Werte sind keine Nullwerte und keine automatisch bestätigten Standardwerte.

### Pose und Alarme

Eine Pose enthält getrennt X/Y/Z in mm, R in Grad sowie J1/J2/J4 in Grad und J3 in mm. Einheiten stehen bereits in Datenfeldnamen oder eindeutigen Typen. Keine implizite Umrechnung aller Gelenke in Radiant.

Jeder Statusdatensatz trägt Sitzungskennung, Empfangszeit und Gültigkeit. Datenalter wird mit einer monotonen Uhr berechnet; UTC-Zeit dient zusätzlich dem exportierten Protokoll. Alarmdaten bleiben vollständig als Rohbytes erhalten; eine Interpretation wird zusätzlich mit ihrer Zuordnungsgrundlage gespeichert.

Gültigkeit unterscheidet `unknown`, `valid`, `stale` und `invalid`. Eine nicht unterstützte Abfrage wird als solche gekennzeichnet. Sie ist nicht gleichbedeutend mit einer plötzlich gestörten Verbindung.

### Verbindung und Bewegung getrennt führen

Verbindung: getrennt, Aufbau, verbunden, gestört.

Bewegung: Zustand unbekannt, Stillstand beobachtet, Jog angefordert, Jog beobachtet, Stopp angefordert, Störung. Die konkreten internen Namen kann die Implementierung konsistent festlegen.

Softwarebereitschaft ergibt sich aus aktuellen Einzelnachweisen und dem gewählten Betriebsmodus. Sie ist kein Ersatz für die physische Sicherheit der Anlage. Bei Neuverbindung sind alte Pose, Alarme, Bereitschaft und offene Bewegungsaufträge ungültig.

### Auftragsstatus

Mindestens unterscheiden: angelegt, gesendet, passende Antwort erhalten, Ausführung beobachtet, abgeschlossen, ausdrücklich abgelehnt, vor Versand abgebrochen und Ausgang unbekannt.

Ein Timeout nach dem Versand bedeutet bei einem verändernden Befehl **Ausgang unbekannt**. Der Befehl kann ausgeführt worden sein. Er wird nicht automatisch erneut gesendet. Abbrechen einer lokalen Warteaufgabe bedeutet ebenfalls nicht, dass der Roboter angehalten wurde.

## 8. Regeln für robuste Kommunikation

1. `connect()` eröffnet ausschließlich den Transport und die Empfangsverwaltung. Keine CMD 161, keine Parameteränderung, kein Queue-Start und kein Alarmlöschen.
2. Ein Empfänger verarbeitet alle vollständigen Frames, prüft Länge und Prüfsumme und verwirft ungültige Daten mit protokolliertem Grund. Eine Nachricht kann mehrere Frames enthalten.
3. Antwortzuordnung prüft ID, Lese-/Schreibrichtung und erwartete Nutzdatenstruktur. Zunächst nur eine normale Anfrage gleichzeitig, bis das Geräteverhalten bekannt ist.
4. Der lokale Auftrag erhält eine eigene Kennung. Sie wird nicht als erfundene Kennung in das bestehende Roboterprotokoll eingefügt.
5. Wo dem Protokoll eine eindeutige Anfragekennung fehlt, können verspätete Antworten gleicher ID mehrdeutig sein. Ein Lock allein löst das nicht. Nach solchem Timeout wird die Sitzung für weitere verändernde Aufträge gesperrt, abgeglichen und nötigenfalls neu aufgebaut; danach neue Diagnose und bewusster Wiederanlauf.
6. Ein Stoppauftrag darf nicht hinter normalen Diagnoseabfragen oder anderen noch nicht gesendeten Schreibaufträgen warten. Nicht gesendete Bewegungsaufträge werden entfernt. Vorher laufende Netzwerkoperationen müssen begrenzt und ihr unklarer Ausgang erkennbar sein. Eine fehlende Jog-Bereitschaft oder ein unbekannter Alarmstatus darf die Stoppanforderung nicht blockieren.
7. Unaufgeforderte gültige Statusmeldungen werden erfasst. Sie dürfen eine offene Anfrage nur erfüllen, wenn sie deren bestätigten Antwortregeln entsprechen. Ihre Aktualität und Bedeutung müssen zum Serververhalten passen.
8. Alarme werden unabhängig von erfolgreichen Poseantworten erfasst. Bei Fehlern wird der relevante Status ungültig; ein alter Nullalarm darf keinen neuen Jog erlauben.
9. Vollständige Rohdaten werden mit Richtung, Nachrichten-/Framegrenzen, Zeit, Sitzung und Fehlern protokolliert. Aufbewahrung ist begrenzt; Diagnoseexport kann die ganze relevante Sitzung enthalten.
10. Fragmentierung innerhalb von WebSocket und Aufteilung eines Dobot-Frames auf mehrere WebSocket-Nachrichten werden unterschieden. Falls Letzteres unterstützt wird, erfolgt es mit begrenztem Restpuffer. Datagramme anderer Transporte werden später nach ihren eigenen Regeln behandelt.

Die konkreten Zeitgrenzen werden als begründete Konfiguration geführt. Es werden keine beliebigen Zeitwerte als bewiesene Sicherheitsgrenze bezeichnet.

## 9. Regeln für Jog, Stopp und Wiederanlauf

### Vor der ersten Bewegung

Ein passendes Profil und aktueller, plausibler Status müssen vorliegen. Die betroffenen Geschwindigkeits-/Beschleunigungsparameter werden bewusst gesetzt und soweit unterstützt bestätigt und zurückgelesen. Der Referenz-/Antriebszustand muss für die gewählte Funktion geklärt sein. Ein Nullalarm allein reicht nicht.

Gelenk-Jog und kartesischer Jog erhalten ihre jeweils eigenen Parameter. Die gemeinsame Prozentzahl ersetzt keine Kenntnis der darunterliegenden Werte. Bei ungeklärtem Zustand bleibt die Diagnose nutzbar, Bewegung aber gesperrt.

### Während der Bewegung

Genau ein manueller Jog ist aktiv. Gegenläufige oder konkurrierende Startanforderungen werden nicht als unabhängige Aufträge nebeneinander ausgeführt. Raumwechsel und relevante Profiländerungen während Jog sind gesperrt oder fordern zuerst einen bestätigten Stopp.

Loslassen, Fokusverlust, Statusverlust und neue relevante Alarmdaten führen zu einer Sperre und einer bestmöglichen Stoppanforderung. Die Software kann bei Netzwerk- oder Prozessausfall keinen garantierten Stopp versprechen. Der vorhandene physische Not-Halt bleibt davon unabhängig.

Es gibt keine unbegrenzte Wiederholung von Bewegungsbefehlen und keine automatische Fortsetzung nach Wiederverbinden. Ein controllerseitiger Watchdog wird nur genutzt, wenn er für diese Steuerung belegt und geprüft ist.

### Woran Erfolg erkennbar ist

Getrennt protokollieren: Versand, passende Antwort und beobachtete Bewegung. Bei J3 werden auch kartesisches Z und die tatsächliche Beobachtung auf Plausibilität geprüft. Das Ausbleiben einer messbaren Änderung bleibt eine Diagnose, keine Aufforderung zu häufigeren oder schnelleren Wiederholungen.

Eine Stoppmeldung unterscheidet „angefordert“, „gesendet“, „beantwortet“ und „Stillstand über frische Daten beobachtet“. Wiederholte unveränderte, aber veraltete Posewerte beweisen keinen Stillstand. Verwendete Toleranzen und Beobachtungsfenster müssen mit Auflösung, Zeitverhalten und Gerätetest begründet werden.

### Fehlerbehandlung

Alarme nicht automatisch löschen. Das dokumentierte CMD-20-Löschformat mit leerer Nutzlast ist gegen die konkrete Firmware zu prüfen. Rückzugsbewegungen bei Richtungsgrenzen brauchen eine verifizierte Alarmdeutung und einen gesonderten Wiederanlaufablauf; die pauschale Sperre wird nicht einfach entfernt.

Homing, Pose-Reset und Firmware-/Betriebsmoduswechsel sind keine allgemeinen Reparaturaktionen. Sie werden nur ergänzt, wenn ihre Funktion und Voraussetzungen für dein Gerät geklärt sind.

## 10. Meilensteine mit klaren Abschlusskriterien

### M0 — Arbeitsbasis und Quellen sichern

Ergebnis: reproduzierbare Umgebung, dokumentierter Ausgangscommit, übernommene Quellen, Umfang V1 und offene Fragen. Bisheriges Verhalten bleibt nachvollziehbar. Keine Live-Verbindung nötig.

Bestanden, wenn Installation und bestehende Tests in einer frischen Umgebung nachvollziehbar sind; Referenzcode und neue Entwicklung klar unterscheidbar sind. Hardware-/Firmwarewerte dürfen hier noch offen sein.

### M1 — Diagnosekern und ausschließlich lesende CLI

Ergebnis: neue Schichten für Protokoll, Transport, Sitzung und Status; Diagnoseexport; künstlicher Transport und Offline-Wiedergabe. Nur geprüfte Leseoperationen sind über die CLI erreichbar. Unbekannte Identitätsabfragen werden nicht geraten.

Software bestanden, wenn Tests beweisen, dass Verbindungsaufbau, Diagnose, Fehler und Beenden keine verändernden Telegramme senden; Mehrfachframes korrekt verarbeitet werden; fehlerhafte Daten und Reconnect alte Statuswerte ungültig machen; der Kern ohne GUI läuft.

Geräteteil bestanden, wenn vollständige echte Antwortfolgen aus deinem M1 gespeichert und Pose-/Alarmstruktur sowie unterstützte Identitäts-/Statusabfragen dokumentiert sind. Soweit Gerätekennung nicht auslesbar ist, muss die manuelle Zuordnung dokumentiert werden. Ausbleibende Antworten werden untersucht; kein automatischer Moduswechsel zur „Reparatur“.

### M2 — Auftragsverwaltung, Bereitschaft und Software-Stopp

Ergebnis: klare Auftragszustände, begrenzte Wartezeiten, Stoppvorrang, Sitzungswechsel und verständliche Sperrgründe. Die notwendigen Schreibformate und ihre Varianten sind dokumentiert. Bewegung bleibt im normalen Startmodus deaktiviert.

Bestanden, wenn verspätete Antworten, fehlende ACKs, Statusalter, konkurrierende Starts, Stopp während wartender Abfrage und Verbindungsabbruch reproduzierbar getestet sind. Ein unbekannter Ausgang wird nicht automatisch wiederholt. Die spätere Hardwarevorbereitung benennt alle noch ungeprüften Voraussetzungen.

### M3 — Kontrollierter Gelenk-Jog am Gerät

Ergebnis: J1/J2/J3/J4 werden einzeln in beiden Richtungen überprüft, zunächst mit bewusst kleinen, für das Gerät begründeten Einstellungen. Keine automatisch durchlaufende Testfahrt.

Bestanden, wenn jede der acht Richtungen mit Ausgangspose, vollständigem Status, Parametern, Befehlsantwort, beobachteter Änderung und Stoppnachweis dokumentiert ist. Gegenrichtung oder fehlende Bewegung wird zuerst erklärt. Noch offene Antriebs-/Referenzfragen verhindern den Abschluss dieses Meilensteins.

### M4 — Kartesischer Jog

Ergebnis: getrennte kartesische Parameter, bestätigte Raumwahl und X/Y/Z/R-Verfahren. Arbeitsraumgrenzen, Armstellung und Einheiten werden berücksichtigt.

Bestanden, wenn jede Richtung in dokumentierter geeigneter Ausgangslage getestet ist; Begrenzung, Ablehnung und Softwarefehler auseinandergehalten werden; Raumwechsel keinen laufenden Jog weiterführt.

### M5 — Bedienoberfläche und erste vollständige Version

Ergebnis: lokale Oberfläche mit Verbindung, Pose, Alarmen, Datenalter, Bereitschaftsgründen, Raumwahl, Haltebedienung, Software-Stopp und Diagnoseexport. Gleicher Controller wie in der CLI.

Bestanden, wenn Fokusverlust, Loslassen, Fehleranzeige, Verbindungswechsel, Beenden und widersprüchliche Eingaben geprüft sind. Die GUI sendet keine Telegramme direkt. Eine dokumentierte Installation aus sauberer Umgebung funktioniert; ein verständlicher kurzer Bedienablauf und die Geräteergebnisse liegen vor.

**Projektregel:** „Softwaretests bestanden“ und „am M1 bestätigt“ stehen separat im Fortschritt. Codex darf einen fehlenden Gerätetest nicht als erledigt markieren. Es gibt keine belastbare Endterminzusage, solange Geräteprofil und Reaktionsverhalten unbekannt sind.

## 11. Konkrete Aufgaben aus den gefundenen Fehlern

Diese Liste wird beim Projektstart in kleine überprüfbare Aufgaben übernommen:

- Mehrfachframes korrekt verarbeiten und beschädigte Längen/Prüfsummen testen.
- Alte Alarm-/Posewerte bei Trennen, Neuverbinden und Statusfehlern ungültig machen.
- Alter der letzten gültigen Antwort bei jeder Bewegungsentscheidung prüfen.
- Alarmabfrage nicht vom Erfolg der Poseabfrage abhängig machen.
- Schreibantworten von Leseantworten unterscheiden; verspätete ACKs testen.
- Verändernde Aufträge ohne Antwort als unklar behandeln.
- Vorbereitungsbefehle nicht versteckt in `connect()` senden.
- Gelenk- und kartesische Parameter getrennt setzen und zurücklesen.
- Software-Stopp priorisieren, konkurrierende Starts verhindern.
- Alarmänderung, Statusverlust und Fokusverlust während Jog behandeln.
- Erfolgsmeldungen an passende Antworten und aktuelle Beobachtungen binden.
- CMD-20-Löschformat korrigieren und Alarmlöschen als eigene Aktion führen.
- Vollständige Rohlogs statt gekürzter Hexdaten exportieren.
- J3-Einheiten, Z-Plausibilität und Statusalter im Z-Nachweis prüfen.
- Alte GUI-Antworten nach Sitzungswechsel ignorieren.
- Fremdcode-Offsets, I/O-Werte und Universalgrenzen nicht still übernehmen.

Die alten 26 Tests werden sinnvoll übernommen oder angepasst. Sie werden durch diese realen Fehlerfälle ergänzt. Reine Tests, die nur den neuen Code nachsprechen, sind kein ausreichender Nachweis.

## 12. Offene Fragen und wann sie gebraucht werden

**Für M0 und Offline-Arbeit:** keine weiteren Hardwaredaten zwingend nötig. Der Umfang ist entschieden. Das vorhandene Quellenpaket reicht für den Beginn.

**Vor dem echten M1-Diagnoseversuch:** tatsächliche URI, alleiniger Verbindungsbesitzer und erreichbarer Roboter; Gerätezuordnung soweit möglich. Eine Typenschildaufnahme oder vorhandene Versionsanzeige hilft, ist aber kein Grund, Offline-Arbeit anzuhalten.

**Vor M3:** vollständige Originalstatusdaten, Hardware-/Firmwarezuordnung, geeigneter Referenz-/Antriebszustand, bestätigte Parametereinheiten und geklärte physische Stoppmöglichkeit. Hier entscheidet sich auch, ob eine herstellerseitige Inbetriebnahmefunktion zusätzlich erforderlich ist.

**Für die Erklärung der alten Armprobleme:** welcher Raum gewählt war, welche Achse/Richtung funktionierte, Ausgangspose und alte Original-Logs. Fehlen diese Daten, bleibt die rückwirkende Ursache teilweise offen; die neue Implementierung muss die Ereignisse künftig nachvollziehbar erfassen.

Eine noch unbekannte Eigenschaft wird nicht durch einen plausibel klingenden Default ersetzt.

## 13. Wie wir mit Codex arbeiten

Der beigefügte Startauftrag beginnt ausschließlich mit **M0 und dem Offline-Softwareteil von M1**. Danach folgt eine konkrete lesende Geräteprüfung als eigener Arbeitsschritt. Noch keine neue Jog-Oberfläche und keine automatisch ausgelösten Bewegungen.

Pro Arbeitspaket: Ziel, betroffene Schichten, erwartetes Verhalten, passende Tests, Ergebnis und offene Geräteprüfung. Technische Entscheidungen werden kurz mit ihrem Grund dokumentiert. Neue Erkenntnisse ändern gezielt das Profil oder die Arbeitsgrundlage, statt als zusätzliche Sonderbedingung an zufälliger Stelle zu landen.

Das Programm entsteht im Repository mit kleinen nachvollziehbaren Änderungen. Die Dokumente hier sind Übergabematerial, keine bereits ausgeführten Projektänderungen. Dieses Paket erstellt weder ein neues Repository noch verändert es deinen vorhandenen GitHub-Code.

## 14. Referenzen und nachvollziehbare Quellen

- Eigene Repositoryanalyse: `DobotM1_Repositoryanalyse_2026-10-26.txt`, insbesondere A1-A4 und B1-B12.
- Eigener geprüfter Code: [Stand 26.10.](https://github.com/Koscher9/DobotM1/tree/7426c4a7621b4f9f936ad76a9bc84702ab92961a) und [Stand 22.10.](https://github.com/Koscher9/DobotM1/tree/8aa03bc4c978722426c27cfff8659bd2b16937db). Der lokale Snapshot bleibt auch bei privatem Repository verfügbar.
- Frühere Recherche: Chat „Dobot M1 Software Recherche“, zugehöriger Rechercheverlauf vom 26.10.2026. Die vollständige ursprüngliche PDF liegt diesem Paket nicht bei.
- [Herstellerprotokoll M1 V1.1](https://download.dobot.cc/development-protocol/dobot-m1/pdf/en/Dobot-M1-Communication-Protocol-V1.1.pdf), [V1.0](https://download.dobot.cc/development-protocol/dobot-m1/pdf/en/Dobot-M1-Communication-Protocol-V1.0.pdf), [Alarmbeschreibung](https://download.dobot.cc/development-protocol/dobot-m1/pdf/alarms/en/Dobot-M1-Alarm-Description.pdf). Unterschiede und redaktionelle Widersprüche bleiben gegen echte Antworten abzugleichen.
- [ARCOR2 M1-Klasse](https://github.com/robofit/arcor2/blob/5fafd77d4dcbacfd914ea33eccdb73055167dcce/src/python/arcor2_dobot/m1.py) und [Basistreiber](https://github.com/robofit/arcor2/blob/5fafd77d4dcbacfd914ea33eccdb73055167dcce/src/python/arcor2_dobot/dobot_api.py): erneut direkt gelesen; Werkzeugversätze, lineares J3, serielle Anbindung und schreibende Initialisierung.
- [Qt-Demo](https://github.com/k61n/dobot-m1-demo/blob/1e53828c97ea19fb351a328b84861878b5be5c24/mydobot.cpp): erneut direkt gelesen; getrennte Parameter, Queueänderungen und unbegrenzte Schleifen.
- [ROS-Projekt](https://github.com/smhaller/dobot-m1/blob/dd46401bc6938ed3e0a6b51fee6a84e8cd0444b6/README.md): README erneut geprüft; Simulation in Gazebo ist dort als offene Aufgabe aufgeführt.

Die vorgeschlagene Architektur und Reihenfolge sind unsere aus diesen Befunden abgeleiteten Entwicklungsentscheidungen. Sie sind keine vom Hersteller bestätigte universelle M1-Lösung.

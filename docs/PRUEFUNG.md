# Fehlerprüfung 0.70 und Umbau

Drei Prüfungen (Plugin-System, Dateien gegen Medien, Kern-Oberfläche) haben zusammen rund 65 Befunde ergeben, viele davon mehrfach. Hier stehen sie zusammengefasst, nach Ursache geordnet, mit der Etappe, in der sie behoben werden. Der Stand je Befund wird hier gepflegt.

## Entscheidung: kein Plugin-System mehr

Das Plugin-System trug genau ein Plugin (Medien), dessen Code dreifach vorlag. Es brachte eigene Fehlerklassen mit, die es ohne Plugins nicht gäbe: Deinstallieren löschte versionierten Code, Datenbank und laufender Zustand liefen auseinander, ein Nutzer konnte ein Plugin für alle abschalten, ein defektes Plugin ließ sich nicht wieder einschalten, der Docker-Weg hatte keine Plugins. Die Medien kommen deshalb fest in den Kern. Aufbau und Optik der Oberfläche bleiben, auch der Umschalter Dateien/Medien.

## Ursachen

1. **Medien neben dem Kern:** eigene Datenquelle, eigene Zugriffsprüfung (nur Eigentum), eigene Bereichslogik beim Abspielen, eigene Darstellung.
2. **Neuladen am falschen Ort:** Aktionen, Upload und Live-Abgleich laden fest den Ordner von `haupt` statt den aktiven Bereich der handelnden Fläche.
3. **Löschen markiert nur den obersten Knoten:** alles darunter gilt weiter als lebend.
4. **Mehrere Tastatur- und Drop-Handler ohne Vorrang.**

## Etappen

### E1 Backend-Kern

Stand: umgesetzt, mit Tests.

| Befund | Behebung |
|---|---|
| Löschen markiert nur den obersten Knoten; Inhalte gelöschter Ordner in Favoriten, Suche, Medien; Hochladen in gelöschte Ordner; Datei aus gelöschtem Ordner einzeln wiederhergestellt verschwindet | Ganzer Teilbaum wird markiert (mit Wurzel des Löschens), Wiederherstellen holt genau diesen Teilbaum zurück; liegt der Elternordner noch im Papierkorb, kommt das Objekt nach "Meine Dateien"; Migration für den Bestand |
| Umbenennen, Verschieben, Auflisten, Hochladen an gelöschten Knoten möglich | Schreib- und Lesewege verlangen lebende Knoten |
| Datei mit dem Namen eines Ordners hängt still am Ordner | Abweisung mit 409 |
| Wiederherstellen ergibt "Bericht.pdf (wiederhergestellt)" | Zusatz vor der Endung, bei Bedarf nummeriert |
| Range doppelt und abweichend (Suffix, 416, Fenster ohne Range, kein If-Range) | Eine Auslieferung für alle Wege (eigene, geteilte, Ablage, Medien) |
| Externe Quellen: als schreibgeschützt beschrieben, aber beschreibbar ohne Version; Download mit Sonderzeichen gibt 500 und liegt ganz im Speicher; kein Änderungsdatum | Externe Quellen sind nur lesbar; Download strömt mit sauberem Dateinamen; Änderungsdatum je Eintrag |
| Validierungsfehler als "[object Object]" | Lesbare deutsche Meldung |
| Suche: kein Favoritenfeld, Umbenennen ohne Neuindizierung, Ordner nicht auffindbar | Suche liefert Favorit, Umbenennen indiziert neu, Ordner werden gefunden |
| Journal: Start bei 0 lädt bis zu 1000 Einträge nach; erste Änderung bei leerem Journal geht verloren | Abfrage des aktuellen Stands als Startpunkt |
| Papierkorb: endgültiges Löschen ohne Journal-Eintrag | Eintrag, damit andere Sitzungen nachziehen |

### E2 Medien im Kern, Plugin-System raus

Stand: umgesetzt, mit Tests. Zusätzlich laufen Herunterladen und ZIP über denselben Lesezugang direkt aus dem Strom (der Browser hält keine Datei mehr im Speicher).

| Befund | Behebung |
|---|---|
| Medien nur für eigene Dateien (Geteilt: 404, Player meldet Codec-Fehler) | Medien nutzen die Lesezugriffsprüfung des Kerns |
| Sitzungstoken in Bild- und Stream-Adressen | Medien-Zugang als eigenes, nur lesendes Cookie für den Medienpfad, an die Sitzung gebunden; Adressen ohne Geheimnis |
| Bilder und Streams 24 h im Browser-Cache ohne Versionsbezug | Adressen tragen den Versionsstand, dadurch dauerhaft cachebar und nach neuer Version sofort neu |
| SVG wird aus der App-Herkunft mit Skript ausgeliefert | Auslieferung mit Sandbox-Richtlinie und ohne Typraten |
| Drei Vorschaugrößen, dreifaches Dekodieren | Zwei feste Stufen aus einem Dekodiervorgang |
| Vollbild lädt das ganze Bild in den Speicher; Vorschau liest die Datei ganz | Vollbild strömt das Original (HEIC einmal umgewandelt und abgelegt); Vorschau liest aus dem Pfad und dekodiert verkleinert |
| Vorschau-Ablage wird nie geleert | Tägliches Aufräumen gegen die vorhandenen Versionen |
| Jeder Fehler im Vorschauweg wird 415 | 404, 415 und 503 getrennt |
| Plugin-Befunde (Deinstallieren löscht Code, Zustand läuft auseinander, Abschalten für alle, kein Wiedereinschalten, Neustart-Rennen, Docker ohne Plugins, ZIP-Rezept, Schema ohne Versionen, drei Kopien, tote Optionen) | Entfallen mit dem Plugin-System; Tabellen `plugin`, `plugin_medien`, `plugin_galerie` werden entfernt (vorher Sicherung) |

### E3 Oberfläche Kern

Stand: umgesetzt und im Browser geprüft. Bewusst offen: die Upload-Karte meldet eine Datei als fertig, sobald sie gesendet ist (der Server speichert danach noch); ein Doppelklick auf einen Ordner bei sehr schneller Antwort (Verdacht, nicht gemessen).

| Befund | Behebung |
|---|---|
| Aktionen und Upload laden den Ordner statt des Bereichs (fremde Liste unter falschem Titel) | Ein Neuladeweg je Fläche, passend zum Bereich |
| Jedes Neuladen zeigt das Ladeskelett: Liste springt nach oben, Filterfeld verliert den Fokus, Umbenennen verliert die Eingabe | Skelett nur beim Ortswechsel, sonst still aktualisieren; Bildlauf bleibt |
| Fehlermeldungen verschwinden beim nächsten Neuladen | Meldungen bleiben bis zum Ortswechsel oder Schließen |
| Globaler Drop landet im unsichtbaren Ordner, auch in Papierkorb, Favoriten, Suche, Geteilt | Ziel ist die aktive Fläche; nicht schreibbare Bereiche nehmen nichts an und sagen es |
| Ordner auf die Liste gezogen verliert die Struktur | Ein Drop-Weg für Liste und Fenster, Ordner werden erkannt |
| Splitscreen: Drop auf den Breadcrumb verschiebt doppelt | Drop wird nur einmal behandelt |
| Auswahl wirkt auf vom Filter versteckte Einträge | Auswahl bleibt auf das Sichtbare beschränkt |
| Auswahlleiste bietet in Geteilt, Favoriten, Extern-Übersicht unerlaubte Aktionen | Eine Rechtetabelle je Bereich für Auswahlleiste und Kontextmenü |
| Verschiebe-Modus überlebt die Navigation, Ziele außerhalb der Ansicht nicht wählbar | Im Modus navigieren, "Hierher verschieben" verschiebt in den offenen Ordner |
| Splitscreen: keine Live-Aktualisierung, Fehler unsichtbar, kein Rückweg aus Extern, Öffnen ohne Wirkung | Alle Flächen hängen am Live-Abgleich, Meldungen je Pane, Rückweg im Breadcrumb, Öffnen spielt ab oder zeigt an |
| Zweiter Upload wird still verworfen; doppelte Namen sprengen die Karte; Systemdateien werden mit hochgeladen | Warteschlange; eindeutige Schlüssel; Systemdateien werden übersprungen |
| Upload-Fehler beendet den Rest | Übrige Dateien laufen weiter, Fehlschläge werden gesammelt gemeldet |
| Abgelaufene Sitzung: Oberfläche bleibt angemeldet | 401 meldet ab und zeigt die Anmeldung |
| Suchtext wirkt vor Enter | Erst Enter sucht |
| Detail: falscher Pfad in Suche und Favoriten, veraltete Werte nach neuer Version; Ordner aus Favoriten mit verkürztem Breadcrumb | Pfad vom Server, Detail zieht beim Neuladen nach |
| Papierkorb: Endgültig im Kontextmenü nur für einen Eintrag, nicht in der Auswahlleiste; Speicheranzeige bleibt alt | Mehrfach endgültig löschen, Speicheranzeige nachladen |
| Geteilt: Einfachklick lädt herunter | Einfachklick markiert und zeigt an, wie überall |
| Anzeige: "1 Dateien", Unterordner als Dateien gezählt, falsche Leerzustände, Teilen-Kennzeichen spät, Splitscreen-Umschalter falsch aktiv, Fehler in Einstellungen im Erfolgsstil, Rollenauswahl zeigt Ungespeichertes, Datenablage-Abfrage läuft weiter | Einzeln behoben |
| Filter, Bildlauf und Medien-Einstellungen gehen beim App-Wechsel verloren | Zustand liegt an der Fläche, nicht am Bauteil |
| Kein iOS-Icon, kein Manifest: als PWA auf dem Telefon ohne Symbol | Vollständiger Satz (ico, PNG, apple-touch-icon 180, Manifest 192/512) |

### E4 Oberfläche Medien

Stand: umgesetzt und im Browser geprüft. Bewusst offen: die Dauer in der Audio-Liste ermittelt weiter der Browser je Zeile (Verdacht auf viele gleichzeitige Verbindungen, nicht gemessen; mit der korrigierten Bereichslogik holt er nur noch den Anfang).

| Befund | Behebung |
|---|---|
| "Alle Medien" wird nie aktualisiert | Hängt am Live-Abgleich |
| Medien baut Lightbox, Video-Ansicht und Audio-Liste nach, mit abweichendem Verhalten | Eine Vollansicht im Kern mit Blättern und Diashow für beide Ansichten; Audio aus Dateien spielt mit Ordnerliste und Pfad |
| Klick auf den laufenden oder beendeten Titel ohne Wirkung | Pause und Neustart |
| Player-Liste überlebt das Abmelden; 401 und 404 erscheinen als Codec-Fehler | Abmelden leert den Player; Meldungen nach Ursache |
| Tastenkollisionen (Leertaste, Escape, Strg+A hinter der Vollansicht) | Offene Vollansicht hat Vorrang, alles andere ruht |
| Audio-Kachel startet und öffnet zugleich, lässt sich nicht ziehen | Klick auf das Wiedergabe-Symbol startet nur |
| Medien-Knopf in Papierkorb, Suche, Extern ohne Hinweis | Knopf dort gesperrt mit Erklärung |
| Video pausiert Audio bei jedem Start | Nur beim Öffnen des Videos |

### E5 Abnahme und Ausrollen

Alle Wege im Browser prüfen (Einzel- und Splitscreen, alle Bereiche, beide Themen), Tests grün, dann Sicherung auf dem Pi, Ausrollen, Prüfung von Gesundheit, Knotenzahl und Pool.

### E6 Mobile Ansicht

Stand: umgesetzt nach dem freigegebenen Entwurf `mockups/mobil.html` (Freigabe 17.10.2026), alle neun Zustände in Telefonbreite in hell und dunkel geprüft. Eigene Oberfläche in `frontend/src/lib/mobil/`, gewählt nach Breite (bis 760 Punkte, Telefon quer über die Höhe); dieselbe Fläche, dieselben Rechte, derselbe Player und dieselbe Vollansicht-Liste wie am Rechner. `viewport-fit=cover` mit Abständen für Aussparung und Wischleiste. Abweichungen vom Entwurf: die Suche heißt "In allen Dateien suchen" (sie sucht immer überall), statt eines Textausschnitts steht "im Inhalt gefunden" (der Suchindex hält keinen Text), externe Quellen gibt es nur am Rechner, "Thema" kennt zusätzlich hell und dunkel.

# Resilienz

Kellerwolke läuft im Dauerbetrieb auf einem kleinen Rechner mit mehreren
Platten. Strom kann mitten in einem Vorgang ausfallen, eine externe Platte kann
zeitweise fehlen. Leitlinie: Die App darf dadurch nie auf die falsche Platte
schreiben, nie still Daten verlieren und nie dauerhaft einfrieren. Lieber sauber
warten und später weitermachen.

## Volume-Marker (Mount-Schutz)

Der Objekt-Pool (die rohen Datei-Blöcke) liegt auf einem bestimmten Laufwerk.
Fällt dessen Mount weg, bleibt unter dem Pfad nur ein leeres Verzeichnis auf
der Systemplatte zurück. Ohne Schutz würde die App dort munter weiterschreiben -
die Daten landeten auf der falschen Platte und der Pool wäre gespalten.

Schutz: Am Wurzelverzeichnis des Pools liegt eine Marker-Datei
`.kellerwolke_pool` mit einer zufälligen UUID. Dieselbe UUID steht in der
Datenbank (Tabelle `speicherort`). Vor jedem Schreiben, Lesen oder Löschen
eines Blocks prüft der BlobStore: existiert die Marker-Datei und passt ihr
Inhalt zur UUID aus der Datenbank?

- passt -> das richtige Laufwerk ist gemountet, Zugriff erlaubt.
- passt nicht / Datei fehlt -> der Pool gilt als **nicht verfügbar**. Es wird
  gar nicht erst geschrieben. Die API antwortet mit HTTP 503 und `Retry-After`,
  die Oberfläche zeigt einen Hinweis. Sobald das Laufwerk wieder da ist, passt
  der Marker von selbst wieder - die App macht ohne Eingriff weiter.

Die Marker-Datei wird nur bei der Erst-Einrichtung (oder beim Adoptieren eines
schon bestehenden Pools) angelegt; dann muss das richtige Laufwerk gemountet
sein. Danach wird sie nie automatisch neu geschrieben: fehlt sie beim Booten,
weil das Laufwerk noch nicht da ist, wartet die App, statt eine falsche
Markierung auf der Systemplatte anzulegen.

Der Marker ist bewusst universell: er funktioniert auf dem Entwickler-Mac mit
einer Platte genauso wie auf dem Zielgerät mit mehreren. Eine reine Geräte-ID-
Prüfung (`st_dev`) würde auf der Einzelplatte falsch auslösen und kommt darum
nicht als Hauptkriterium zum Einsatz.

## Nicht-blockierende Blob-Ein-/Ausgabe

Jeder Plattenzugriff (Schreiben, Lesen, Löschen eines Blocks, auch die
Verfügbarkeitsprüfung) läuft in einem begrenzten Thread-Pool, nicht direkt im
Event-Loop. So friert eine hängende Platte nie den Loop und damit die ganze
App ein - andere Anfragen laufen ungestört weiter.

Dazu ein Zeitlimit pro Zugriff: ein Grundwert plus ein größenabhängiger
Aufschlag, damit legitime große Transfers nicht abgebrochen werden, ein echter
Hänger aber irgendwann als nicht verfügbar (HTTP 503) zurückkommt, statt eine
Anfrage ewig festzuhalten. Die begrenzte Pool-Größe deckelt zugleich, wie viele
Threads eine hängende Platte maximal binden kann. Einstellbar über
`KELLERWOLKE_IO_THREADS`, `KELLERWOLKE_IO_TIMEOUT` und
`KELLERWOLKE_IO_MIN_DURCHSATZ`.

## Datenablage verschieben

Den Objekt-Pool auf ein anderes Laufwerk zu verschieben ist gehärtet: Erst wird
geprüft, dass die Quelle erreichbar ist, das Ziel beschreibbar ist und nicht im
Quellordner liegt (oder umgekehrt) und genug Platz frei ist. Dann wird kopiert,
das Ziel bekommt einen frischen Volume-Marker mit eigener Identität, und erst
danach werden aktiver Pfad und Marker in der Datenbank atomar umgestellt. Die
Quelle wird zuletzt gelöscht - stürzt der Vorgang mittendrin ab, liegen alle
Blöcke noch an der Quelle, es geht nichts verloren. Die alte Quelle bleibt durch
ihren alten Marker als "falsches Laufwerk" erkennbar.

## Boot-Robustheit und Autostart

Fehlt das Laufwerk beim Hochfahren noch (es wird oft erst nach dem Dienst
gemountet), stürzt nichts ab: Der Dienst startet sauber, meldet den Pool als
nicht verfügbar und wartet. Es wird in diesem Fall keine Marker-Datei angelegt -
so entsteht nie eine falsche Markierung auf der Systemplatte. Sobald das
Laufwerk da ist, ist der Pool von selbst wieder verfügbar.

Damit die Anwendung nach einem Neustart von allein wieder hochkommt, richtet
`tools/systemd-einrichten.sh` auf dem Zielgerät einen systemd-Dienst ein, der
`./start.sh` als einzige Startlogik nutzt (Datenbank, Backend, Frontend). Die
Datenbank im Docker-Container hat zusätzlich `restart: unless-stopped`. Auf dem
Entwickler-Mac entfällt der systemd-Schritt; dort wird mit `./start.sh`
gearbeitet.

## Nächste Schritte

- Konsistenz-Prüfung und Reparatur (verwaiste Blöcke nach Stromausfall).

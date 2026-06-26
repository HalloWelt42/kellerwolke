# Kellerwolke

Die eigene Wolke im Keller - ein schlanker, selbst gehosteter Datei-Speicher für Familie und kleine Haushalte.

Kellerwolke legt Dateien sicher ab, hält jede Version vor und gibt sie über eine Web-Oberfläche und über WebDAV wieder heraus. Alle Daten bleiben auf dem eigenen Server - volle Hoheit, kein fremder Dienst.

## Stand

Frühe Aufbauphase. In dieser Phase entsteht der Datei-Kern mit Web-Oberfläche und WebDAV. Echter Geräte-Abgleich (Desktop, Mobil) ist architektonisch vorbereitet, aber noch nicht umgesetzt.

## Technik

- Backend: Python mit FastAPI, reine REST-Schnittstelle
- Frontend: Svelte 5 als eigenständige Oberfläche
- Metadaten: PostgreSQL
- Speicher: inhaltsadressierte Ablage je Konto, sparsam durch Mehrfachverweise
- Betrieb: Docker

Oberfläche und Schnittstelle sind strikt getrennt: das Backend liefert nur Daten, die Oberfläche ist austauschbar.

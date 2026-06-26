# Sync-Vorbereitung

Echter Geräte-Abgleich (Desktop, Mobil) ist in dieser Phase noch nicht gebaut,
aber so vorbereitet, dass er sich später anstöpseln lässt - ohne großen Umbau.
Dieses Dokument beschreibt die Bausteine und wie ein künftiger Client sie nutzt.

## Die drei Bausteine

1. **Stabile Knoten-IDs (UUID).** Jeder Knoten hat eine pfadunabhängige UUID.
   Umbenennen und Verschieben ändern nur Name oder Elternverweis, nie die ID.
   So unterscheidet ein Client ein Verschieben von Löschen-plus-Neuanlegen.
2. **Änderungs-Journal pro Nutzer.** Jede Mutation hängt einen Eintrag an die
   Tabelle `aenderung` an: eine monoton steigende `seq`, der `knoten_id`, der
   Typ (`erstellt`, `geaendert`, `verschoben`, `geloescht`) und die `version_id`.
   Das Journal ist die Quelle, gegen die ein Client difft.
3. **Inhalts-Hash und ETag.** Jede Version trägt ihren Inhalts-Hash; der Knoten
   trägt einen ETag (die Versions-UUID). Damit erkennt ein Client, ob sich der
   Inhalt geändert hat, und kann Konflikte feststellen.

## So arbeitet ein künftiger Client

1. Beim ersten Lauf den ganzen Baum holen und die höchste gesehene `seq` merken.
2. Danach regelmäßig `GET /api/v1/sync/journal?seit=N` abrufen (N = letzte
   gesehene `seq`). Die Antwort enthält alle Änderungen seit N in Reihenfolge.
3. Je Eintrag handeln: bei `erstellt`/`geaendert` die Datei per Download holen,
   bei `verschoben` lokal verschieben/umbenennen, bei `geloescht` lokal entfernen.
4. Lokale Änderungen umgekehrt hochladen (Upload, Umbenennen, Verschieben,
   Löschen über die bestehende REST-API). Bei Konflikt (lokaler ETag passt nicht
   zum Server-ETag) eine Konfliktkopie anlegen.

Der Endpunkt `GET /api/v1/sync/journal` ist bereits vorhanden und getestet; er
liefert das Journal pro angemeldetem Nutzer, streng isoliert.

## Chunk-Sollbruchstelle

Heute gilt: eine Datei ist genau ein Block (`chunk`-Tabelle mit einer Zeile je
Version). Das Datenmodell trägt die Chunk-Liste aber schon. Später werden neue
Dateien in mehrere inhaltsadressierte Blöcke zerlegt; ein Client lädt dann nur
die ihm fehlenden Blöcke (Delta-Sync). Bestandsdateien bleiben als Ein-Block-
Einträge gültig - keine Migration nötig.

## Was für echten Sync noch fehlt

- Ein nativer Client (Desktop/Mobil), der lokal einen Ordner beobachtet.
- Eine festgelegte Konfliktstrategie (Konfliktkopie ist der einfache Anfang).
- Optional Push statt Poll (etwa über eine offene Verbindung), wenn das Pollen
  zu träge wird.
- Echtes Delta-Chunking im Speicherkern (die Sollbruchstelle ist vorbereitet).

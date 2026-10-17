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

## Gekoppelte Geräte

Ein Telefon oder Tablet meldet sich nicht mit dem Passwort an, sondern wird gekoppelt; so liegt dort kein Passwort.

1. Am Rechner unter Einstellungen, Geräte erzeugt `POST /api/v1/geraete/kopplung` einen Code (acht Zeichen, zehn
   Minuten gültig, nur einmal; ein neuer ersetzt einen offenen). Der QR-Code daneben öffnet die Kellerwolke mit
   `#koppeln=<Code>`; der Code steht hinter dem `#` und geht so in kein Protokoll.
2. Das Gerät löst ihn ohne Anmeldung ein: `POST /api/v1/geraete/koppeln` mit `code`, `name` und `art` (`webapp`
   oder `browser`). Die Antwort trägt den Schlüssel `kw_geraet_...`, einmal im Klartext.
3. Der Schlüssel geht danach im Kopf `X-Kellerwolke-Sitzung` mit wie ein Sitzungs-Token, auch für den Lese-Cookie
   der Inhaltsadressen. Er handelt mit den Rechten des Kontos und läuft nicht ab.
4. `GET /api/v1/geraete` listet die Geräte mit "zuletzt gesehen" und Adresse, `PATCH`/`DELETE /api/v1/geraete/{id}`
   benennt um oder trennt. Abmelden auf dem Gerät selbst (`POST /api/v1/auth/logout`) trennt es ebenfalls.

Falsche Codes werden je Absender gebremst (nach fünf Fehlern in zehn Minuten fünf Minuten Pause, Antwort 429).
Auf dem iPhone hat die Web-App vom Home-Bildschirm einen eigenen Speicher, getrennt von Safari: dort wird der Code
eingetippt, der QR-Code koppelt den Browser.

## Fortsetzbare Uploads

Ein Telefon verliert die Verbindung oder legt die App schlafen; eine große Datei soll dann nicht von vorn beginnen.
Dafür gibt es Uploads in Teilen:

1. `POST /api/v1/uploads` mit `name`, `parent_id`, `groesse` und auf Wunsch `pruefsumme` (sha256 hex) legt den
   Upload an und liefert seine Kennung.
2. `PATCH /api/v1/uploads/{id}` je Teil, Kopf `Upload-Offset` = bisher empfangene Bytes, Körper = das Teil roh.
   Setzt das Teil falsch an, kommt 409 mit dem richtigen `Upload-Offset` im Kopf.
3. Nach einer Unterbrechung sagt `GET /api/v1/uploads/{id}` (Feld `empfangen`), wo es weitergeht; auch was mitten
   im abgebrochenen Teil schon ankam, zählt. `GET /api/v1/uploads` listet alle offenen Uploads des Kontos.
4. Mit dem letzten Byte wird die Datei eingetragen wie jeder Upload (gleicher Name: neue Version); die Antwort trägt
   `fertig` und den Knoten. Passt die Prüfsumme nicht, wird nichts eingetragen (422).

`DELETE /api/v1/uploads/{id}` bricht ab. Ruhende Uploads räumt die tägliche Pflege nach
`KELLERWOLKE_TEILE_TAGE` Tagen weg (Vorgabe 7); die Teile liegen unter `KELLERWOLKE_TEILE_PFAD`, außerhalb des
Blob-Pools.

## Was für echten Sync noch fehlt

- Ein nativer Client (Desktop/Mobil), der lokal einen Ordner beobachtet.
- Eine festgelegte Konfliktstrategie (Konfliktkopie ist der einfache Anfang).
- Optional Push statt Poll (etwa über eine offene Verbindung), wenn das Pollen
  zu träge wird.
- Echtes Delta-Chunking im Speicherkern (die Sollbruchstelle ist vorbereitet).

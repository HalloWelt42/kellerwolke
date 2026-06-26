# Deployment

Der vollständige Stack (Datenbank, Backend, Frontend) läuft über
`compose.pi.yml`. Nur das Frontend wird nach außen veröffentlicht; es leitet
`/api` und `/webdav` intern an das Backend weiter.

## Bauen und starten

```
docker compose -f compose.pi.yml up -d --build
```

Danach ist die Oberfläche unter `http://localhost:8470` erreichbar. Beim ersten
Start wird ein Admin-Konto angelegt (Standard `admin`/`admin`, für den Betrieb
unbedingt ändern).

## Konfiguration

Wird über Umgebungsvariablen gesetzt (oder eine `.env` neben `compose.pi.yml`):

- `KELLERWOLKE_FRONTEND_PORT` - Host-Port der Oberfläche
- `KELLERWOLKE_ADMIN_NAME`, `KELLERWOLKE_ADMIN_PASSWORT` - erstes Admin-Konto
- `KELLERWOLKE_DB_PASS`, `KELLERWOLKE_APP_SECRET` - Geheimnisse, echte Werte setzen
- `KELLERWOLKE_EXTERN_PFAD` - Pfad des read-only eingehängten Datenträgers
- `KELLERWOLKE_MAX_UPLOAD` - Obergrenze je Upload in Bytes

## Auf einem Server mit großer Platte

- App-Daten (Datenbank-Volume, Objekt-Pool) gehören auf ein ext4-Dateisystem.
  Der Objekt-Pool liegt als Bind-Mount unter `./data/objects` - das Projekt also
  auf der schnellen, zuverlässigen Platte ablegen, nicht auf exFAT.
- Den großen, bestehenden Datenträger read-only einbinden: setze
  `KELLERWOLKE_EXTERN_PFAD` auf seinen Mount-Pfad. Er erscheint im Container unter
  `/extern`. Danach hängt ein Admin ihn als externe Quelle ein, per
  `POST /api/v1/admin/externe-quelle` mit `pfad: /extern`. Die Daten werden nur
  gelesen, nie kopiert oder verändert.
- Ports pro Installation eindeutig wählen, damit nichts mit anderen Diensten
  kollidiert.

## Wiederherstellung ohne die App

Auch ohne laufende App lassen sich alle Dateien zurückgewinnen:

```
python3 tools/recovery.py --ausgabe /pfad/zur/sicherung
```

Das Werkzeug liest die Datenbank read-only und den Objekt-Pool und baut den
Dateibaum jedes Nutzers wieder auf.

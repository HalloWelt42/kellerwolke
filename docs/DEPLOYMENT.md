# Deployment

## Betrieb auf dem Pi (so läuft die Kellerwolke)

Die Datenbank läuft in Docker, das Backend als Dienst daneben, vorne ein Caddy im Container (`docker compose`
Profil `web`): er liefert die gebaute Oberfläche aus, reicht `/api` und `/webdav` ans Backend weiter und spricht
TLS mit einem Zertifikat aus der Hausstelle. Die Dienste richtet `tools/systemd-einrichten.sh` einmal ein
(`kellerwolke-db`, `kellerwolke-backend`, `kellerwolke-web`, zusammengefasst in `kellerwolke.target`).

| Adresse | Zweck |
|---|---|
| `http://<pi>:KELLERWOLKE_FRONTEND_PORT` | Oberfläche ohne TLS (bisherige Adresse) |
| `https://<pi>:KELLERWOLKE_TLS_PORT` | Oberfläche mit TLS; nötig für das iPhone (App auf dem Home-Bildschirm, Teilen-Menü) |
| `http://<pi>:KELLERWOLKE_BACKEND_PORT` | Backend direkt (Schnittstelle, WebDAV) |

Vom Mac aus:

- `tools/zertifikat.sh` stellt das Blattzertifikat aus der Hausstelle (mkcert) aus und bringt es nach
  `data/zertifikate` auf dem Pi; `--pruefen` meldet, wenn es in weniger als 60 Tagen abläuft. Der Schlüssel der
  Hausstelle bleibt auf dem Mac. Ein Telefon, das der Hausstelle schon vertraut (etwa für die Kiste), vertraut damit
  auch der Kellerwolke; sonst das Hauszertifikat einmal installieren und in den Einstellungen unter Info,
  Zertifikatsvertrauen einschalten.
- `tools/ausrollen.sh` rollt einen gepushten Stand aus: Sicherung der Datenbank (`tools/pi/sichern.sh`), Stand holen,
  auf dem Pi Abhängigkeiten, Oberfläche bauen, Dienste neu starten und prüfen (`tools/pi/ausrollen.sh`).

## Alles in Containern (Alternative)

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
- `KELLERWOLKE_VORSCHAU_PFAD` - Ablage der Vorschau- und Vollbilder (abgeleitet, jederzeit neu erzeugbar, Standard `data/vorschau`)
- `KELLERWOLKE_VORSCHAU_GLEICHZEITIG` - wie viele Vorschauen gleichzeitig entstehen (Standard 2)
- `KELLERWOLKE_FFMPEG` - Pfad zu ffmpeg für Standbilder aus Videos; ohne ffmpeg zeigen Videos nur ihr Symbol

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

## Autostart nach Neustart

Für den Dauerbetrieb richtet `./tools/systemd-einrichten.sh` einen systemd-Dienst
ein, der die App nach einem Neustart automatisch wieder hochfährt. Wie sich die
Anwendung verhält, wenn ein Laufwerk fehlt oder der Strom mitten in einem Vorgang
ausfällt, beschreibt [RESILIENZ.md](RESILIENZ.md).

## Wiederherstellung ohne die App

Auch ohne laufende App lassen sich alle Dateien zurückgewinnen:

```
python3 tools/recovery.py --ausgabe /pfad/zur/sicherung
```

Das Werkzeug liest die Datenbank read-only und den Objekt-Pool und baut den
Dateibaum jedes Nutzers wieder auf.

## Viele Dateien einspielen (Übernahme aus einer früheren App)

`tools/einspielen.py` spielt Dateien nach einem Plan ein, auf dem Rechner der Kellerwolke neben der laufenden App und
durch den Speicherdienst (Journal, Begleitdateien, Suchindex wie beim Hochladen). Plan und Dateien liegen in einem
Ordner; der Plan (`plan.json`, Aufbau in `backend/module/einspielen/plan.py`) nennt je Datei das Ziel unter "Meine
Dateien", die Prüfsumme (SHA-256), frühere Stände (werden Versionen), Inhaltstyp, erzeugende App, Felder und für eine
Begleitdatei ihre Hauptdatei mit Rolle und Zusatz.

```bash
backend/.venv/bin/python tools/einspielen.py /mnt/data/einspielen/<lauf>/plan.json               # Vorschau
backend/.venv/bin/python tools/einspielen.py /mnt/data/einspielen/<lauf>/plan.json --ausfuehren  # einspielen
```

Die Vorschau sagt je Eintrag neu, vorhanden, fortsetzen, Konflikt oder fehlt und ändert nichts. Überschrieben wird
nie: liegt am Ziel etwas anderes, bleibt es, und der Eintrag entfällt. Jeder Stand wird nur mit seiner Prüfsumme
eingetragen; nach einem Abbruch setzt ein neuer Lauf beim nächsten Stand fort. Vorher sichern (`tools/pi/sichern.sh`).

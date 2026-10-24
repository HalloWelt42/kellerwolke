---
zweck: "Die eigene Dateiwolke: legt Dateien mit allen Versionen ab, gibt sie über Oberfläche und WebDAV heraus und ist das Konto, mit dem man sich bei allen Apps des Verbunds anmeldet."
geraet: [pi]
abhaengigkeiten: []
daten:
  - "Pi: Datenbank (PostgreSQL in Docker, Volume pgdata des Projekts aus `COMPOSE_PROJECT_NAME` der .env, unter /var/lib/docker auf der Systemplatte)"
  - "Pi: Dateipool {{umgebung:KELLERWOLKE_OBJEKT_PFAD}} auf der externen Platte (inhaltsadressierte Blöcke aller Konten)"
  - "Pi: {{wurzel}}/data mit Vorschaubildern, Teilen laufender Uploads und dem Zertifikat (abgeleitet bzw. neu ausstellbar)"
sicherung:
  - "Datenbank: jedes Ausrollen legt vorher einen Auszug `kellerwolke_db_backup_<Zeit>.sql.gz` neben den Ordner {{wurzel}} (tools/pi/sichern.sh); das Werkzeug Sicherungen holt diese Auszüge täglich nach ~/Sicherungen/kellerwolke/pi. Eine regelmäßige Sicherung gibt es nicht (Stand 24.10.2026: nur Auszüge vom 18. und 20.10.)"
  - "Dateipool: keine Sicherung (Stand 24.10.2026); fällt die externe Platte aus, sind die Dateien weg"
schluessel_orte:
  - "Pi: {{wurzel}}/.env, Modus 0600: KELLERWOLKE_DB_PASS, KELLERWOLKE_APP_SECRET, KELLERWOLKE_ADMIN_PASSWORT (erstes Konto)"
  - "Pi: `{{wurzel}}/data/zertifikate/kellerwolke-schluessel.pem`, Modus 0600 (Schlüssel des Blattzertifikats)"
  - "Datenbank: Konten, Geräteschlüssel und App-Schlüssel der Apps (angelegt unter Einstellungen, Zugänge; nur einmal sichtbar)"
einrichten: einrichten.sh
stand: fda6ca9
---

# Kellerwolke

## Zweck

Die Kellerwolke ist der Dateispeicher des Hauses und zugleich das Konto für alles: Man meldet sich mit dem
Kellerwolke-Konto bei jeder App des Verbunds an, und jede App bekommt hier ihren App-Schlüssel, mit dem sie Dateien
liest und Ergebnisse als Begleitdateien neben die Quelle legt (etwa Transkripte neben Aufnahmen). Dateien liegen mit
allen Versionen im Dateipool, Metadaten in PostgreSQL; die Oberfläche läuft im Browser und als Web-App auf dem iPhone,
WebDAV bindet die Ablage im Finder ein.

Ohne Kellerwolke kann sich niemand bei den Apps anmelden, und die Apps finden ihre Dateien nicht.

Auf dem Pi laufen drei Teile: die Datenbank in Docker, das Backend als Dienst (uvicorn) und vorne ein Caddy in Docker,
der die gebaute Oberfläche ausliefert, `/api` und `/webdav` ans Backend reicht und TLS mit dem Zertifikat der
Hausstelle spricht. Adresse für alle: {{adresse}}.

## Was sie braucht

- Pi nach [[Grundlage Pi]], dazu dort Python mit `python3-venv` und Node.js mit npm (die Oberfläche wird auf dem Pi
  gebaut) und die externe Platte (Dateipool, siehe [[Grundlage Pi]]).
- Mac nach [[Grundlage Mac]] mit der Hausstelle: von dort kommen Zertifikat und Ausrollen.
- Sonst keine andere App; die Kellerwolke ist die erste im Verbund.

## Neu einrichten

Zwei Wege. Aus der Sicherung: `.env` und ein Auszug der Datenbank kommen zurück, der Dateipool auf der externen
Platte bleibt, wo er ist; dann sind Konten, App-Schlüssel und Geräte wie vorher. Frisch: neue `.env` mit neuen
Geheimnissen, leere Datenbank; danach bekommt jede App einen neuen App-Schlüssel und jedes Gerät koppelt neu.

### 1. Klon und .env auf dem Pi

```
git clone {{repo}} {{wurzel}}
```

Aus der Sicherung: die alte `.env` nach `{{wurzel}}/.env` legen. Frisch: `bash tools/setup-env.sh` schreibt eine `.env`
mit Ports und Projektnamen aus dem Ordner ({{port:backend}} bis {{port:datenbank}}) und zufälligen
Geheimnissen. Dazu die Werte des Hauses aus der privaten Wahrheit, die `handbuch ziel kellerwolke --env` am Mac ausgibt:
Bindung (`KELLERWOLKE_BIND`), Dateipool (`KELLERWOLKE_OBJEKT_PFAD`), Pool nur auf der externen Platte
(`KELLERWOLKE_POOL_MUSS_EXTERN`, nie ersatzweise auf die Systemplatte), Port mit TLS (`KELLERWOLKE_TLS_PORT`) und die
Hauptadresse (`KELLERWOLKE_HAUPTADRESSE`); dazu `KELLERWOLKE_ADMIN_NAME` und `KELLERWOLKE_ADMIN_PASSWORT` für das erste
Konto. Dann `chmod 600 .env`.

Probe: `stat -c %a {{wurzel}}/.env` meldet 600, und `grep -c '^KELLERWOLKE_TLS_PORT=' {{wurzel}}/.env` meldet 1.

### 2. Zertifikat vom Mac

Am Mac im Klon `tools/zertifikat.sh`: stellt aus der Hausstelle das Blattzertifikat für die Adresse und die Namen des
Pi aus und legt es mit der Hausstelle nach `{{wurzel}}/data/zertifikate`. Ziel, Ordner und Namen kommen aus der
privaten Wahrheit (`tools/ziel.sh` fragt `handbuch ziel kellerwolke`).

Probe: `tools/zertifikat.sh --pruefen` endet mit 0 (Zertifikat da und noch mindestens 60 Tage gültig).

### 3. Einrichten auf dem Pi

`./einrichten.sh` im Klon: Python-Umgebung, Oberfläche bauen, Datenbank starten, dann die systemd-Dienste
`kellerwolke-db`, `kellerwolke-backend` und `kellerwolke-web` unter `kellerwolke.target` einrichten und starten
(braucht sudo). Danach startet die Kellerwolke mit dem Pi von selbst und wird nach einem Absturz neu gestartet.

Probe: `curl -s http://127.0.0.1:{{port:backend}}/api/health` meldet `"version": "{{fassung}}"`, und vom Mac meldet
`curl -s --cacert "$(mkcert -CAROOT)/rootCA.pem" {{adresse}}/api/health` dasselbe.

### 4. Datenbank aus der Sicherung

Nur auf dem Weg aus der Sicherung, sofort nach Schritt 3 und bevor jemand etwas hochlädt: Backend anhalten, die frisch
angelegten Tabellen leeren, den Auszug einspielen, Backend starten.

```
sudo systemctl stop kellerwolke-backend
docker compose --env-file .env exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "drop schema public cascade; create schema public"'
gunzip -c <auszug>.sql.gz | docker compose --env-file .env exec -T db sh -c 'psql -q -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
sudo systemctl start kellerwolke-backend
```

Probe: `docker compose --env-file .env exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At -c "select count(*) from knoten"'`
nennt die Zahl der Knoten wie vorher, und die Oberfläche zeigt die Dateien.

### 5. Konto, Geräte und Apps

Im Browser {{adresse}} öffnen und mit dem ersten Konto anmelden (frisch: Name und Passwort aus der `.env`, danach das
Passwort in der Oberfläche ändern). Das iPhone vertraut der Hausstelle (siehe [[Grundlage Mac]]) und koppelt sich mit
einem Code (Einstellungen, Geräte). Jede App bekommt ihren App-Schlüssel unter Einstellungen, Zugänge, wenn sie
eingerichtet wird; der Schlüssel ist nur einmal sichtbar und geht direkt in die Einrichtung der App.

Probe: Anmeldung im Browser gelingt, unter Einstellungen, Zugänge stehen die Apps (frisch: noch keine).

## Sicherung und Rückspielen

Datenbank: `tools/ausrollen.sh` ruft vor jedem Ausrollen auf dem Pi `tools/pi/sichern.sh`; das legt einen geprüften,
gepackten Auszug (`pg_dump`) als `kellerwolke_db_backup_<Zeit>.sql.gz` neben den Ordner der App. Aufgeräumt wird
dort nicht. Das Werkzeug Sicherungen am Mac holt diese Auszüge täglich nach `~/Sicherungen/kellerwolke/pi`; den Stand
zeigt `~/Sicherungen/LIESMICH.md`. Eine regelmäßige Sicherung unabhängig vom Ausrollen gibt es nicht (Stand
24.10.2026: die jüngsten Auszüge stammen vom 18. und 20.10.). Zurückspielen wie in Schritt 4.

Dateipool: keine Sicherung (Stand 24.10.2026). Die Blöcke liegen unter {{umgebung:KELLERWOLKE_OBJEKT_PFAD}} nach ihrer Prüfsumme;
solange Platte und ein Auszug der Datenbank da sind, holt `python3 tools/recovery.py --ausgabe <ordner>` den Dateibaum
jedes Kontos auch ohne laufende App heraus. Ohne die Platte sind die Dateien verloren.

Zertifikat und `.env`: das Zertifikat stellt `tools/zertifikat.sh` jederzeit neu aus; die `.env` gehört in die
Sicherung des Pi (siehe [[Grundlage Pi]]).

## Wenn etwas klemmt

- Die Kellerwolke startet nicht und meldet den Pool: die externe Platte ist nicht eingehängt. Mit
  `KELLERWOLKE_POOL_MUSS_EXTERN` legt sie den Pool nie ersatzweise auf die Systemplatte; Platte einhängen
  (siehe [[Grundlage Pi]]), dann `sudo systemctl restart kellerwolke-backend`.
- Das Backend ist abgestürzt: systemd startet es neu (`sudo systemctl status kellerwolke-backend`,
  `journalctl -u kellerwolke-backend`).
- Das iPhone meldet ein ungültiges Zertifikat: es vertraut der Hausstelle nicht, oder das Zertifikat ist abgelaufen
  (`tools/zertifikat.sh --pruefen`, dann `tools/zertifikat.sh` und `sudo systemctl restart kellerwolke-web`).
- Ein Code zum Koppeln "gilt nicht": er stammt aus einer anderen Kellerwolke (etwa der Entwicklung am Mac); die Apps
  hängen an {{adresse}}.
- Das Ausrollen bricht am Ende mit "meldet ... statt ..." ab: Adresse oder Port im Ziel (`handbuch ziel kellerwolke`)
  passen nicht zur `.env` auf dem Pi, oder der Dienst `kellerwolke-web` läuft nicht.

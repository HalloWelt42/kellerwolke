# Kellerwolke für eigene Apps

Eigene Apps (Transkription, Stimmenausgabe und weitere) legen ihre Dateien in der Kellerwolke ab. Sie melden sich mit
einem App-Schlüssel an (`Authorization: Bearer kw_app_...`), den das Konto unter Einstellungen, Zugänge ausstellt, und
sprechen die Ablage-Schnittstelle unter `/api/v1/ablage`.

## Rechte

- Je App ein Zugang mit Rechten je Ordner: lesen oder schreiben. Vorgabe beim Anlegen: schreiben in `Apps/<App>`,
  lesen in `Apps`. Weitere Ordner gibt das Konto frei (gemeinsame Arbeitsordner).
- Was außerhalb der Rechte liegt, gibt es für die App nicht (404). Lesen ja, schreiben nein: 403.
- Überschreiben nur mit dem zuletzt gelesenen Stand (`If-Match`), sonst 428; `If-None-Match: *` legt nur neu an.
- Löschen legt in den Papierkorb; endgültig löscht nur das Konto.
- Verschieben und Umbenennen (`POST /api/v1/ablage/knoten/{id}/ort` mit `{ordner_id, name}`) gehen innerhalb der
  Schreibrechte; Begleitdateien ziehen mit, ein freigegebener Ordner selbst bleibt stehen.

## Begleitdateien

Ergebnisse liegen neben ihrer Quelle (Entscheidung 17.10.2026: "zusammengehörige dateien immer beieinander ablegen, so
geht nix verloren"). Ein Begleiter gehört zu genau einer Hauptdatei und hat eine Rolle (`transkript`, `untertitel`,
`sprache`, ...); je Hauptdatei und Rolle gibt es höchstens einen.

**Name:** Stamm der Hauptdatei und ein Zusatz, den die App nennt. `Runde.wav` mit Zusatz `.transkript.json` ergibt
`Runde.transkript.json`, mit `.srt` ergibt `Runde.srt`. Ist der Name schon vergeben, kommt der volle Name davor:
`Runde.wav.transkript.json`. Den Namen vergibt die Kellerwolke; Apps schreiben über Hauptdatei und Rolle, nie über einen
Pfad.

**Die Gruppe hält zusammen**, auf allen Wegen (Oberfläche, Apps, WebDAV):

| Vorgang | Wirkung |
|---|---|
| Hauptdatei umbenennen | Begleiter folgen dem neuen Namen (`Runde.srt` wird `Planung.srt`) |
| ein Mitglied verschieben | die ganze Gruppe zieht um |
| Name am Ziel belegt | nichts ändert sich, 409 mit dem belegten Namen |
| Hauptdatei in den Papierkorb | Begleiter gehen mit; der Papierkorb zeigt eine Zeile für die Gruppe |
| Begleiter allein in den Papierkorb | nur er; beim Wiederherstellen kommt er neben seine Hauptdatei, auch wenn sie inzwischen woanders liegt |
| wiederherstellen mit belegtem Namen | Zusatz "(wiederhergestellt)" wie bei jeder Datei |
| endgültig löschen, Papierkorb leeren | Begleiter gehen mit |
| aus der Gruppe lösen | der Begleiter wird eine gewöhnliche Datei; die Herkunft bleibt |
| neuer Begleiter, während der alte im Papierkorb liegt | der neue übernimmt die Rolle, der alte kommt als gewöhnliche Datei zurück |

Ein Begleiter hat selbst keine Begleiter; Ergebnisse zu einem Ergebnis gehören an die Hauptdatei.

**Schnittstelle:**

| Weg | Zweck |
|---|---|
| `GET /api/v1/ablage/knoten/{haupt}/begleiter` | Begleiter einer Hauptdatei, nach Rolle |
| `PUT /api/v1/ablage/knoten/{haupt}/begleiter/{rolle}?zusatz=.transkript.json` | Begleiter schreiben (Körper roh); neu, oder neue Version mit `If-Match` |
| `POST /api/v1/ablage/knoten/{haupt}/begleiter/{rolle}` mit `{knoten_id, zusatz}` | eine vorhandene Datei der App wird Begleiter und kommt neben die Hauptdatei |
| `POST /api/v1/ablage/knoten/{id}/loesen` | ein Begleiter wird eine gewöhnliche Datei (etwa: Aufnahme in den Papierkorb, Transkript behalten) |
| `POST /api/v1/dateien/{id}/loesen` (Oberfläche) | Begleiter aus der Gruppe lösen |

Schreiben braucht Leserecht auf die Hauptdatei und Schreibrecht in ihrem Ordner. Jeder Begleiter trägt zusätzlich die
Herkunft (von der Hauptdatei, Art = Rolle). Knoten in Listen und Einzelabfragen nennen `haupt_id` und `rolle`, in der
Oberfläche zählt `begleiter_anzahl` die lebenden Begleiter einer Hauptdatei. Regeln und Namen stehen an einer Stelle in
`backend/module/speicher/begleiter.py`, die Durchsetzung im Speicherdienst.

## Aktionen und Anfragen

Apps bieten dem Konto an, was sie mit Dateien können (Entscheidung 17.10.2026); das Dateimenü der Kellerwolke zeigt es
unter "Mit Apps". Eine Anfrage heißt: App X soll Aktion A auf Datei D ausführen. Sie entsteht im Dateimenü, oder eine
App gibt sie an eine andere weiter.

**Recht je Anfrage:** Solange eine Anfrage offen ist (wartet oder läuft, nicht abgelaufen), darf die angefragte App
genau diese Datei lesen und ihre Begleiter schreiben, sonst nichts außerhalb ihrer Ordner. Dafür schickt sie bei jedem
Zugriff den Kopf `X-Kellerwolke-Anfrage: <id>` mit ihrem App-Schlüssel; ist die Anfrage fertig, abgebrochen oder
abgelaufen, gibt es 403. Ein zweites Geheimnis gibt es nicht.

| Weg | Zweck |
|---|---|
| `PUT /api/v1/ablage/aktionen` | die App meldet ihre Aktionen (ersetzt die Liste) und die Adresse ihrer Oberfläche |
| `GET /api/v1/ablage/anfragen?warten=25` | wartende Anfragen abholen, älteste zuerst; ohne Anfrage wartet es bis zu 30 s; zugleich Lebenszeichen |
| `POST /api/v1/ablage/anfragen/{id}/annehmen` | ab jetzt läuft sie |
| `PATCH /api/v1/ablage/anfragen/{id}` | Fortschritt (0 bis 1), Meldung, Ende (`fertig` mit `ergebnis_id` oder `fehler`); 409, wenn abgebrochen: dann aufhören |
| `GET /api/v1/ablage/anfragen/{id}` | Stand einer Anfrage (etwa nach einem Neustart oder für eine weitergegebene) |
| `POST /api/v1/ablage/anfragen` mit `{app, aktion, knoten_id, optionen}` | an eine andere App weitergeben; wer weitergibt, muss die Datei lesen und neben ihr schreiben dürfen. `optionen` (höchstens 10, Namen als Kennung) bekommt die angefragte App beim Abholen unverändert, etwa `{"sprache": "en"}` |
| `GET /api/v1/dateien/{id}/aktionen` (Oberfläche) | was die Apps mit dieser Datei können |
| `POST /api/v1/anfragen` (Oberfläche) | Anfrage stellen; bei Aktionen zum Öffnen kommt die Adresse in der App zurück |
| `GET /api/v1/anfragen`, `DELETE .../{id}`, `POST .../aufraeumen` (Oberfläche) | ansehen, abbrechen, aufräumen |

**Aktion:** Kennung, Titel (und `titel_erneut`, wenn der Begleiter ihrer Rolle schon da ist, etwa "Neu
transkribieren"), Symbol aus Font Awesome, Inhaltstypen (auch `audio/*`), Art und Rolle. Art `hintergrund`: die App
holt die Anfrage ab und arbeitet; Art `oeffnen`: die Kellerwolke führt den Browser zu `<adresse>/anfrage/<id>`, die
App nimmt sie dort an. An einem Begleiter erscheinen die Aktionen zum Öffnen seiner Rolle; sie gelten dann für die
Hauptdatei.

**Fristen:** im Hintergrund 24 Stunden, zum Öffnen 12 Stunden. Wer innerhalb von 90 Sekunden abgeholt hat, gilt als
erreichbar; sonst zeigt die Oberfläche, dass die Anfrage auf die App wartet.

## Anmeldung an Apps und Dateiwahl

Apps haben keine eigenen Konten; der Mensch meldet sich in einer App mit seinem Kellerwolke-Konto an (Passwort oder
gekoppeltes Gerät). Diese Anmeldung gilt nur zur Erkennung (Entscheidung 17.10.2026, kein Dauerrecht über das Konto):

- `POST /api/v1/auth/login` mit `fuer_app` und `POST /api/v1/geraete/koppeln` mit `fuer_app` liefern eine Sitzung
  oder einen Geräteschlüssel, der den Namen der App trägt. `GET /api/v1/auth/status` nennt ihn in `app`.
- Mit einer solchen Anmeldung gibt es keine Dateien, keine Zugänge, keine Verwaltung (403); Status und Abmelden gehen.
- Die Geräteliste der Kellerwolke zeigt, für welche App ein Gerät gekoppelt ist.

**Dateiwahl:** In der App wählt der Mensch eine Datei aus seinem ganzen Konto. Dafür schickt die App ihren
App-Schlüssel und die Anmeldung des Menschen an genau dieser App (`X-Kellerwolke-Sitzung`) zusammen:

| Weg | Zweck |
|---|---|
| `GET /api/v1/ablage/wahl?ordner=<id>` | Ordnerkette und Einträge (nur Name, Typ, Größe, Inhaltstyp, Datum, Begleiter), ohne Ordner das ganze Konto von oben |
| `POST /api/v1/ablage/wahl` mit `{knoten_id, aktion}` | die Wahl stellt eine Anfrage an diese App; ab dann gilt das Recht je Anfrage |

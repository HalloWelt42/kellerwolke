# Kellerwolke für eigene Apps

Eigene Apps (Transkription, Stimmenausgabe und weitere) legen ihre Dateien in der Kellerwolke ab. Sie melden sich mit
einem App-Schlüssel an (`Authorization: Bearer kw_app_...`), den das Konto unter Einstellungen, Zugänge ausstellt, und
sprechen die Ablage-Schnittstelle unter `/api/v1/ablage`.

## Rechte

- Je App ein Zugang mit Rechten je Ordner: lesen oder schreiben. Vorgabe beim Anlegen: schreiben in `Apps/<App>`,
  lesen in `Apps`. Weitere Ordner gibt das Konto frei (gemeinsame Arbeitsordner).
- Was außerhalb der Rechte liegt, gibt es für die App nicht (404). Lesen ja, schreiben nein: 403.
- Überschreiben nur mit dem zuletzt gelesenen Stand (`If-Match`), sonst 428; `If-None-Match: *` legt nur neu an.
- Löschen legt in den Papierkorb; endgültig löscht nur das Konto. Was die App unter einem lesbaren Ordner gelöscht
  hat, sieht sie dort (`GET /api/v1/ablage/papierkorb?ordner={id}`, zuletzt gelöschtes zuerst, je Eintrag die
  mitgelöschten Begleiter), liest es (`GET /api/v1/ablage/papierkorb/{id}/inhalt`) und holt es mit Schreibrecht an
  den alten Ort zurück (`POST /api/v1/ablage/knoten/{id}/wiederherstellen`, Begleiter mit, ein vergebener Name
  bekommt einen Zusatz). Was in einem gelöschten Ordner steckt, zählt mit ihm.
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

## Verweise

Jede Datei gibt es genau einmal (Entscheidung 20.11.2026). Braucht eine App eine Datei, die schon anderswo liegt, legt
sie in ihrem Ordner einen Verweis darauf an statt einer Kopie: die Telegram-Ablage etwa gibt Bilder in die Bildablage
und legt im Chat-Ordner nur den Verweis ab. Ein Verweis ist ein eigener Eintrag (`typ: "verweis"`), klar getrennt von
echten Daten: er hat Name, Ort und eigene Felder, aber keinen eigenen Inhalt und belegt keinen Platz.

| Regel | Wirkung |
|---|---|
| Ziel | immer eine lebende Datei desselben Kontos; zeigt das angegebene Ziel selbst auf etwas, gilt dessen Original (keine Ketten). Ordner sind kein Ziel (422) |
| Anlegen | Schreibrecht im Ordner des Verweises, Leserecht auf das Original; sonst 403 bzw. 404 |
| Wiederholen | derselbe Aufruf (gleicher Pfad, gleiches Original) liefert den vorhandenen Verweis; ein anderer Eintrag unter dem Namen: 409 |
| Lesen | folgt dem Original: Inhalt, Versionen, Größe, `sha256`, ETag und Inhaltstyp sind dessen |
| Schreiben | nur am Original; Schreiben auf einen Verweis: 409 |
| Verweis löschen | nur der Verweis kommt in den Papierkorb, das Original bleibt |
| Original löschen | alle lebenden Verweise darauf gehen mit in den Papierkorb (wie Begleiter, auch beim Löschen eines Ordners mit dem Original), Wiederherstellen holt sie an ihren Ort zurück (ist der Ordner weg, nach oben; ein vergebener Name bekommt einen Zusatz), endgültig löschen nimmt sie mit |
| verwaist | das Original fehlt oder liegt im Papierkorb: `verwaist: true`, kein Inhalt (404), nur noch entfernen |
| Suche | zählt Verweise nicht doppelt: trifft das Original, fehlt der Verweis; treffen nur Verweise, steht einer da |
| WebDAV | zeigt Verweise als Dateien mit dem Inhalt des Originals, nur lesend (PUT, DELETE, MOVE: 403); verwaiste fehlen |

**Schnittstelle:**

| Weg | Zweck |
|---|---|
| `POST /api/v1/ablage/verweis` mit `{ziel_id, pfad}` | Verweis anlegen; `pfad` ist Ordner und Name, etwa `Apps/Telegram/Familie/2026-11/2026-11-03 Oma.jpg`; der Ordner muss es geben (`POST /api/v1/ablage/ordner`) |
| `GET /api/v1/ablage/knoten/{id}/verweise` | lebende Verweise auf eine Datei, soweit die App sie sehen darf |
| `GET /api/v1/ablage/knoten/{id}/loeschfolgen` | was Löschen mitnähme: `{folgen: [{id, name, art: begleiter oder verweis, pfad, zu_id, rolle}], verborgen}`; `verborgen` zählt, was die App nicht sehen darf |
| `GET /api/v1/ablage/papierkorb?ordner={id}` | je Eintrag zusätzlich `verweise`: die mitgenommenen (soweit sichtbar) |
| `POST /api/v1/dateien/loeschfolgen` mit `{ids}` (Oberfläche) | Folgenvorschau vor dem Löschen, je Folge mit Ordnerpfad `ort` |
| `GET /api/v1/dateien/{id}/verweise` (Oberfläche) | Verweise auf eine Datei mit Ordnerpfad und App |

Knoten in Listen und Einzelabfragen tragen dafür `typ` (`ordner`, `datei`, `extern`, `verweis`), `ziel_id` (beim
Verweis das Original, sonst `null`), `verwaist` und `sha256`; in der Oberfläche zählt `verweis_anzahl` die lebenden
Verweise auf eine Datei (im Papierkorb: die mitgenommenen), `verweis_app` nennt die App, die einen Verweis angelegt hat. Regeln an einer Stelle in
`backend/module/speicher/verweise.py`, die Durchsetzung im Speicherdienst.

## Prüfsumme: gibt es den Inhalt schon?

Jede Version kennt den sha256 ihres ganzen Inhalts (`sha256` an Knoten und Versionen). Vor dem Hochladen fragt eine App,
ob es den Inhalt im lesbaren Bereich schon gibt, und legt dann einen Verweis an statt einer Kopie:

| Weg | Zweck |
|---|---|
| `GET /api/v1/ablage/pruefsumme/{sha256}` | lebende Dateien, deren aktuelle Version genau diesen Inhalt hat, soweit die App sie lesen darf, älteste zuerst; je Treffer `id`, `pfad`, `groesse`, `sha256`. Verweise zählen nicht. Leer heißt: nichts Lesbares. Kein gültiger sha256 (64 Zeichen hex, klein): 422 |

Ablauf für eine App: sha256 der Datei berechnen, fragen; bei einem Treffer `POST /api/v1/ablage/verweis` mit dessen
`id`, sonst hochladen (in einem Stück oder fortsetzbar) und dabei die Prüfsumme mitgeben.

## Fortsetzbare Uploads

Große Dateien (Videos, lange Sprachnachrichten) gehen in Teilen und setzen nach einer Unterbrechung am empfangenen Stand
fort, mit der Sitzung oder mit dem App-Schlüssel:

| Weg | Zweck |
|---|---|
| `POST /api/v1/uploads` mit `{name, parent_id, groesse, pruefsumme, etag, nur_neu}` | Upload anlegen, liefert `id` und `empfangen` |
| `PATCH /api/v1/uploads/{id}` mit Kopf `Upload-Offset` und dem Teil als Körper | anhängen; mit dem letzten Byte ist die Datei eingetragen, die Antwort trägt `knoten` (mit `sha256`) |
| `GET /api/v1/uploads/{id}`, `GET /api/v1/uploads` | Stand (wo es weitergeht), offene Uploads |
| `DELETE /api/v1/uploads/{id}` | abbrechen |

Für Apps gelten dieselben Regeln wie beim Schreiben in einem Stück: nur in Ordnern mit Schreibrecht (sonst 403), nicht
auf oberster Ebene (404). Eine vorhandene Datei nur mit dem zuletzt gelesenen Stand (`etag`) oder gar nicht
(`nur_neu: true`); ohne beides 428, ein veralteter Stand oder `nur_neu` bei vorhandener Datei 412. Geprüft wird beim
Anlegen und noch einmal mit dem letzten Teil (Recht entzogen: 403, Stand inzwischen anders: 412, gesperrt: 423); dann
bleibt der Upload liegen, bis die App ihn abbricht. Mit `pruefsumme` wird nur eingetragen, wenn der Inhalt genau diesen
sha256 hat (sonst 422). Ein Upload gehört dem, der ihn begonnen hat: die App sieht nur ihre eigenen, die Anmeldung nur
ihre. Ruhende Uploads räumt die Kellerwolke nach einigen Tagen weg.

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
| `GET /api/v1/ablage/apps` | die Apps desselben Kontos (Namen der App-Zugänge und ob aktiv, ohne Rechte und Schlüssel), etwa als Auswahl in den Einstellungen einer App oder als Ziel einer Weitergabe |
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

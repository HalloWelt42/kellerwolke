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
| `POST /api/v1/dateien/{id}/loesen` (Oberfläche) | Begleiter aus der Gruppe lösen |

Schreiben braucht Leserecht auf die Hauptdatei und Schreibrecht in ihrem Ordner. Jeder Begleiter trägt zusätzlich die
Herkunft (von der Hauptdatei, Art = Rolle). Knoten in Listen und Einzelabfragen nennen `haupt_id` und `rolle`, in der
Oberfläche zählt `begleiter_anzahl` die lebenden Begleiter einer Hauptdatei. Regeln und Namen stehen an einer Stelle in
`backend/module/speicher/begleiter.py`, die Durchsetzung im Speicherdienst.

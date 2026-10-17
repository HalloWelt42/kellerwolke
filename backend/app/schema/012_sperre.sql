-- Bearbeitungssperre für lange Arbeiten an einer Datei (schneiden, vertonen): eine App hält sie bis zu einer Zeit,
-- andere Apps dürfen solange nicht schreiben, lesen bleibt frei. Läuft von selbst ab, wenn die App sie nicht erneuert
-- (etwa nach einem Absturz).

CREATE TABLE IF NOT EXISTS sperre (
    knoten_id  uuid PRIMARY KEY REFERENCES knoten(id) ON DELETE CASCADE,
    zugang_id  uuid NOT NULL REFERENCES app_zugang(id) ON DELETE CASCADE,
    app        text NOT NULL,
    grund      text NOT NULL DEFAULT '',
    seit       timestamptz NOT NULL DEFAULT now(),
    bis        timestamptz NOT NULL
);

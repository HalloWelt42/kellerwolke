-- Metadaten je Datei und Herkunft zwischen Dateien, für Apps (und später die Oberfläche).
-- Beides hängt an Knoten-Kennungen und übersteht Umbenennen und Verschieben.

CREATE TABLE IF NOT EXISTS datei_meta (
    knoten_id    uuid PRIMARY KEY REFERENCES knoten(id) ON DELETE CASCADE,
    inhaltstyp   text,                                  -- MIME-Typ, vom Schreiber angegeben oder aus dem Namen
    app          text,                                  -- App, die zuletzt geschrieben hat
    felder       jsonb NOT NULL DEFAULT '{}'::jsonb,    -- freie Felder der App (Sprache, Stimme, Dauer ...)
    geaendert_am timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS datei_meta_felder_idx ON datei_meta USING gin (felder);

-- Bezug "zu entstand aus von": zum Beispiel ein Transkript zu einer Aufnahme, ein geschnittener Ton aus dem Original.
CREATE TABLE IF NOT EXISTS herkunft (
    von_id      uuid NOT NULL REFERENCES knoten(id) ON DELETE CASCADE,
    zu_id       uuid NOT NULL REFERENCES knoten(id) ON DELETE CASCADE,
    art         text NOT NULL CHECK (art ~ '^[a-z][a-z_]{0,39}$'),
    app         text,
    erstellt_am timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (von_id, zu_id, art),
    CHECK (von_id <> zu_id)
);

CREATE INDEX IF NOT EXISTS herkunft_zu_idx ON herkunft (zu_id);

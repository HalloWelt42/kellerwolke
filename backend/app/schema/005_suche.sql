-- Volltext ueber Name und (sofern extrahierbar) Inhalt, pro Nutzer gefiltert.
-- Deutsche Konfiguration; Pflege asynchron nach dem Upload.

CREATE TABLE IF NOT EXISTS such_index (
    knoten_id   uuid PRIMARY KEY REFERENCES knoten(id) ON DELETE CASCADE,
    besitzer_id uuid NOT NULL REFERENCES benutzer(id) ON DELETE CASCADE,
    name_tsv    tsvector,
    inhalt_tsv  tsvector
);

CREATE INDEX IF NOT EXISTS such_name_idx   ON such_index USING gin (name_tsv);
CREATE INDEX IF NOT EXISTS such_inhalt_idx ON such_index USING gin (inhalt_tsv);
CREATE INDEX IF NOT EXISTS such_besitzer_idx ON such_index (besitzer_id);

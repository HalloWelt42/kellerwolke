-- Volltext ueber den (sofern extrahierbaren) Inhalt, pro Nutzer gefiltert; Namen siehe 015_suche_namen.sql.
-- Deutsche Konfiguration; Pflege asynchron nach dem Upload.

CREATE TABLE IF NOT EXISTS such_index (
    knoten_id   uuid PRIMARY KEY REFERENCES knoten(id) ON DELETE CASCADE,
    besitzer_id uuid NOT NULL REFERENCES benutzer(id) ON DELETE CASCADE,
    inhalt_tsv  tsvector
);

CREATE INDEX IF NOT EXISTS such_inhalt_idx ON such_index USING gin (inhalt_tsv);
CREATE INDEX IF NOT EXISTS such_besitzer_idx ON such_index (besitzer_id);

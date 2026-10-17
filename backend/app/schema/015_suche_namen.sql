-- Namen sucht die Suche direkt am Knoten: die Spalte rechnet sich bei jedem Anlegen und Umbenennen selbst nach,
-- für Dateien wie Ordner. Der Suchindex hält nur noch den Inhalt (nachträglich und nur, wo er lesbar ist).

ALTER TABLE knoten ADD COLUMN IF NOT EXISTS name_tsv tsvector
    GENERATED ALWAYS AS (to_tsvector('german', regexp_replace(name, '[-._/\\]+', ' ', 'g'))) STORED;

CREATE INDEX IF NOT EXISTS knoten_name_tsv_idx ON knoten USING gin (name_tsv);

ALTER TABLE such_index DROP COLUMN IF EXISTS name_tsv;

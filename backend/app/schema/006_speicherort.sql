-- Aktiver Speicherort des Objekt-Pools (genau eine Zeile, id=1). Erlaubt das
-- Verschieben der Datenablage auf ein anderes Laufwerk ohne Code-Aenderung;
-- der BlobStore liest seine Wurzel beim Start aus dieser Zeile.

CREATE TABLE IF NOT EXISTS speicherort (
    id           integer PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    pfad         text NOT NULL,
    geaendert_am timestamptz NOT NULL DEFAULT now()
);

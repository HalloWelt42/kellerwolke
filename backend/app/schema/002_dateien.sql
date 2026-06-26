-- Logischer Baum (Sicht des Nutzers) und die Bruecke zu den physischen Bloecken.
-- typ='extern' haengt einen bestehenden Verzeichnisbaum read-only ein (extern_pfad);
-- dessen Kinder werden live von der Platte gelesen, nicht hier gespeichert.

CREATE TABLE IF NOT EXISTS knoten (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    besitzer_id         uuid NOT NULL REFERENCES benutzer(id) ON DELETE CASCADE,
    parent_id           uuid REFERENCES knoten(id) ON DELETE CASCADE,
    name                text NOT NULL,
    typ                 text NOT NULL,              -- 'ordner' | 'datei' | 'extern'
    aktuelle_version_id uuid,                        -- nur fuer typ='datei'
    etag                text,
    extern_pfad         text,                        -- nur fuer typ='extern' (read-only)
    geloescht           boolean NOT NULL DEFAULT false,
    erstellt_am         timestamptz NOT NULL DEFAULT now(),
    geaendert_am        timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS knoten_parent_idx
    ON knoten (besitzer_id, parent_id) WHERE NOT geloescht;

-- Namens-Eindeutigkeit je Ordner, case-insensitiv (Sync-Sicherheit ueber Plattformen).
CREATE UNIQUE INDEX IF NOT EXISTS knoten_name_idx
    ON knoten (besitzer_id, parent_id, lower(name)) WHERE NOT geloescht;

CREATE TABLE IF NOT EXISTS version (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    knoten_id   uuid NOT NULL REFERENCES knoten(id) ON DELETE CASCADE,
    groesse     bigint NOT NULL,
    inhalt_hash text NOT NULL,
    erstellt_am timestamptz NOT NULL DEFAULT now(),
    erstellt_von uuid REFERENCES benutzer(id)
);

CREATE INDEX IF NOT EXISTS version_knoten_idx ON version (knoten_id);

-- Inhaltsadressierte Bloecke, Dedup pro Nutzer isoliert.
CREATE TABLE IF NOT EXISTS blob (
    besitzer_id uuid NOT NULL REFERENCES benutzer(id) ON DELETE CASCADE,
    hash        text NOT NULL,
    groesse     bigint NOT NULL,
    refcount    integer NOT NULL DEFAULT 0,
    PRIMARY KEY (besitzer_id, hash)
);

-- Sollbruchstelle fuer spaeteren Delta-Sync: heute genau ein Chunk je Version.
CREATE TABLE IF NOT EXISTS chunk (
    version_id  uuid NOT NULL REFERENCES version(id) ON DELETE CASCADE,
    reihenfolge integer NOT NULL,
    blob_hash   text NOT NULL,
    groesse     bigint NOT NULL,
    PRIMARY KEY (version_id, reihenfolge)
);

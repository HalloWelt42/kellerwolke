-- Aenderungs-Journal pro Nutzer (Kern der Sync-Vorbereitung).
-- Ein kuenftiger Client fragt "Aenderungen seit seq N".

CREATE TABLE IF NOT EXISTS aenderung (
    seq         bigserial PRIMARY KEY,
    besitzer_id uuid NOT NULL REFERENCES benutzer(id) ON DELETE CASCADE,
    knoten_id   uuid NOT NULL,
    typ         text NOT NULL,   -- 'erstellt' | 'geaendert' | 'verschoben' | 'geloescht'
    version_id  uuid,
    zeit        timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS aenderung_besitzer_idx ON aenderung (besitzer_id, seq);

-- Fortsetzbare Uploads in Teilen (vor allem vom Telefon): ein Upload kennt Ziel, Name, Gesamtgröße und auf Wunsch die
-- Prüfsumme; die Teile liegen bis zum letzten Stück in einer Datei außerhalb des Blob-Pools (KELLERWOLKE_TEILE_PFAD).
-- Wie viel angekommen ist, sagt die Größe dieser Datei: das überlebt auch einen Neustart mitten im Teil.

CREATE TABLE IF NOT EXISTS upload (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    besitzer_id uuid NOT NULL REFERENCES benutzer(id) ON DELETE CASCADE,
    parent_id   uuid REFERENCES knoten(id) ON DELETE CASCADE,
    name        text NOT NULL,
    groesse     bigint NOT NULL CHECK (groesse >= 0),
    pruefsumme  text CHECK (pruefsumme ~ '^[0-9a-f]{64}$'),
    erstellt_am timestamptz NOT NULL DEFAULT now(),
    zuletzt_am  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS upload_besitzer_idx ON upload (besitzer_id);

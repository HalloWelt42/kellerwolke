-- Favoriten: ein Nutzer markiert eigene Knoten als Favorit (Schnellzugriff).

CREATE TABLE IF NOT EXISTS favorit (
    benutzer_id uuid NOT NULL REFERENCES benutzer(id) ON DELETE CASCADE,
    knoten_id   uuid NOT NULL REFERENCES knoten(id) ON DELETE CASCADE,
    erstellt_am timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (benutzer_id, knoten_id)
);

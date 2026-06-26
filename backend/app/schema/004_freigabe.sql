-- Freigaben als Referenz-Semantik: Modell jetzt, Oberflaeche spaeter.
-- typ='intern' teilt mit einem Konto, typ='link' erzeugt einen Freigabe-Link.

CREATE TABLE IF NOT EXISTS freigabe (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    knoten_id       uuid NOT NULL REFERENCES knoten(id) ON DELETE CASCADE,
    typ             text NOT NULL,                  -- 'intern' | 'link'
    ziel_benutzer_id uuid REFERENCES benutzer(id) ON DELETE CASCADE,
    token           text,
    rechte          text NOT NULL DEFAULT 'lesen',  -- 'lesen' | 'schreiben'
    passwort_hash   text,
    ablauf          timestamptz,
    erstellt_am     timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS freigabe_knoten_idx ON freigabe (knoten_id);
CREATE UNIQUE INDEX IF NOT EXISTS freigabe_token_idx ON freigabe (token) WHERE token IS NOT NULL;

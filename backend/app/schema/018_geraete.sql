-- Gekoppelte Geräte: Telefon und Tablet bleiben angemeldet, ohne dass dort ein Passwort liegt. Jedes Gerät hat einen
-- eigenen Schlüssel (in der Datenbank nur sein SHA-256) und handelt mit den Rechten des Kontos. Gekoppelt wird mit
-- einem kurzlebigen Code, den das Konto am Rechner erzeugt; er gilt einmal und wenige Minuten.

CREATE TABLE IF NOT EXISTS geraet (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    benutzer_id      uuid NOT NULL REFERENCES benutzer(id) ON DELETE CASCADE,
    name             text NOT NULL,
    art              text NOT NULL CHECK (art IN ('webapp', 'browser')),
    schluessel_hash  text NOT NULL UNIQUE,
    gekoppelt_am     timestamptz NOT NULL DEFAULT now(),
    zuletzt_am       timestamptz,
    zuletzt_adresse  text
);

CREATE INDEX IF NOT EXISTS geraet_benutzer_idx ON geraet (benutzer_id);

-- Ein Kopplungscode. Eingelöst trägt er das neue Gerät, damit der Rechner sieht, dass es geklappt hat; auch wenn das
-- Gerät später getrennt wird, bleibt er eingelöst.
CREATE TABLE IF NOT EXISTS kopplung (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    benutzer_id  uuid NOT NULL REFERENCES benutzer(id) ON DELETE CASCADE,
    code_hash    text NOT NULL UNIQUE,
    erstellt_am  timestamptz NOT NULL DEFAULT now(),
    ablauf       timestamptz NOT NULL,
    eingeloest_am timestamptz,                              -- einmal eingelöst, nie wieder
    geraet_id    uuid REFERENCES geraet(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS kopplung_benutzer_idx ON kopplung (benutzer_id);

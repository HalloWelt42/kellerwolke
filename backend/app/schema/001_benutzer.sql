-- Konten und Sitzungen. Identitaet als UUID (keine fortlaufenden Codes).

CREATE TABLE IF NOT EXISTS benutzer (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name          text NOT NULL,
    kuerzel       text,
    passwort_hash text,
    rolle         text NOT NULL DEFAULT 'mitglied' CHECK (rolle IN ('admin', 'mitglied')),
    aktiv         boolean NOT NULL DEFAULT true,
    quota_bytes   bigint,                              -- NULL = unbegrenzt (vorgesehen, nicht erzwungen)
    erstellt_am   timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS benutzer_name_idx ON benutzer (lower(name));

CREATE TABLE IF NOT EXISTS sitzung (
    token_hash  text PRIMARY KEY,
    benutzer_id uuid NOT NULL REFERENCES benutzer(id) ON DELETE CASCADE,
    erstellt_am timestamptz NOT NULL DEFAULT now(),
    ablauf      timestamptz NOT NULL
);

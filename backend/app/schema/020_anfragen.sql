-- Aktionen der Apps und Anfragen an sie (Entscheidung 17.10.2026): eine App meldet, was sie mit welchen Dateien kann;
-- das Konto (oder eine andere App) stellt eine Anfrage "App X, Aktion A, Datei D". Die App holt offene Anfragen selbst
-- ab. Solange eine Anfrage offen ist, darf die App genau diese Datei lesen und ihre Begleiter schreiben.

ALTER TABLE app_zugang ADD COLUMN IF NOT EXISTS adresse text;          -- Oberfläche der App, für Aktionen zum Öffnen
ALTER TABLE app_zugang ADD COLUMN IF NOT EXISTS gemeldet_am timestamptz; -- letztes Lebenszeichen beim Abholen

CREATE TABLE IF NOT EXISTS app_aktion (
    zugang_id    uuid NOT NULL REFERENCES app_zugang(id) ON DELETE CASCADE,
    kennung      text NOT NULL CHECK (kennung ~ '^[a-z][a-z_]{0,39}$'),
    titel        text NOT NULL,
    titel_erneut text,                                      -- wenn der Begleiter der Rolle schon da ist
    symbol       text NOT NULL,
    typen        text[] NOT NULL,                           -- Inhaltstypen, auch mit Stern (audio/*)
    art          text NOT NULL CHECK (art IN ('hintergrund', 'oeffnen')),
    rolle        text,                                      -- Begleiter, um den es geht (transkript, sprache ...)
    reihenfolge  int NOT NULL DEFAULT 0,
    PRIMARY KEY (zugang_id, kennung)
);

CREATE TABLE IF NOT EXISTS anfrage (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    benutzer_id  uuid NOT NULL REFERENCES benutzer(id) ON DELETE CASCADE,
    zugang_id    uuid NOT NULL REFERENCES app_zugang(id) ON DELETE CASCADE,
    aktion       text NOT NULL,
    knoten_id    uuid NOT NULL REFERENCES knoten(id) ON DELETE CASCADE,
    von          text NOT NULL,                             -- konto oder Name der App, die weitergab
    art          text NOT NULL DEFAULT 'hintergrund' CHECK (art IN ('hintergrund', 'oeffnen')),
    zustand      text NOT NULL DEFAULT 'wartet'
                 CHECK (zustand IN ('wartet', 'laeuft', 'fertig', 'fehler', 'abgebrochen')),
    fortschritt  real,
    meldung      text,
    ergebnis_id  uuid REFERENCES knoten(id) ON DELETE SET NULL,
    erstellt_am  timestamptz NOT NULL DEFAULT now(),
    geaendert_am timestamptz NOT NULL DEFAULT now(),
    gueltig_bis  timestamptz NOT NULL
);

CREATE INDEX IF NOT EXISTS anfrage_zugang_idx ON anfrage (zugang_id, zustand);
CREATE INDEX IF NOT EXISTS anfrage_konto_idx ON anfrage (benutzer_id, erstellt_am DESC);
CREATE INDEX IF NOT EXISTS anfrage_knoten_idx ON anfrage (knoten_id);

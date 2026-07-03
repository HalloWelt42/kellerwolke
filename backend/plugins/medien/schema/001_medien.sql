-- Eigene Tabelle des Medien-Plugins (Nutzer-Voreinstellungen der Ansicht).
CREATE TABLE IF NOT EXISTS einstellung (
    benutzer_id   uuid PRIMARY KEY REFERENCES public.benutzer(id) ON DELETE CASCADE,
    standard_modus text NOT NULL DEFAULT 'kachel_gross',
    geaendert_am  timestamptz NOT NULL DEFAULT now()
);

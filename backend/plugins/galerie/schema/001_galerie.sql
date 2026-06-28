-- Eigene Tabellen der Bildergalerie. Liegen im Schema plugin_galerie (der Lader
-- setzt den search_path), nur unqualifiziert schreiben. FKs auf den Kern
-- ausdruecklich auf public.* - so bleibt DROP SCHEMA plugin_galerie CASCADE
-- vollstaendig und gefahrlos beim Deinstallieren.

CREATE TABLE IF NOT EXISTS einstellung (
    benutzer_id      uuid PRIMARY KEY REFERENCES public.benutzer(id) ON DELETE CASCADE,
    standard_modus   text NOT NULL DEFAULT 'kachel_gross',
    diashow_sekunden integer NOT NULL DEFAULT 4,
    autoplay         boolean NOT NULL DEFAULT false,
    geaendert_am     timestamptz NOT NULL DEFAULT now()
);

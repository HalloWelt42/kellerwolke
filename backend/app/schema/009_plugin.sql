-- Kern-Registry der entdeckten Plugins. Jedes Plugin besitzt ZUSAETZLICH ein
-- eigenes Postgres-Schema plugin_<id> fuer seine Tabellen; hier steht nur der
-- Verwaltungs-Eintrag. Neu entdeckte Plugins sind standardmaessig inaktiv und
-- werden bewusst im Admin-Panel freigeschaltet ("Nichts fest verdrahten").

CREATE TABLE IF NOT EXISTS plugin (
    id             text PRIMARY KEY,
    name           text NOT NULL,
    version        text NOT NULL,
    kategorie      text NOT NULL DEFAULT 'ansicht-app',
    aktiv          boolean NOT NULL DEFAULT false,
    defekt         text,            -- Fehlertext, falls Laden/Migration scheiterte (sonst NULL)
    quelle         text NOT NULL DEFAULT 'repo',  -- repo | upload
    schema_version integer NOT NULL DEFAULT 0,
    entdeckt_am    timestamptz NOT NULL DEFAULT now()
);

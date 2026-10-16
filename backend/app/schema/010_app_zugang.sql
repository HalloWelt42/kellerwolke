-- Zugang für Apps: je App ein Schlüssel, ausgestellt für ein Konto. In der Datenbank liegt nur der SHA-256 des
-- Schlüssels. Die Dateien der App liegen im Baum des Kontos unter Apps/<App>.
--
-- Rechte hängen an Ordnern (Knoten-Kennungen, stabil bei Umbenennen und Verschieben), nicht an einem festen
-- App-Zweig: so können mehrere Apps gemeinsame Arbeitsordner beschreiben. Ein Recht gilt für den Ordner und alles
-- darunter; schreiben schließt lesen ein.

CREATE TABLE IF NOT EXISTS app_zugang (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    benutzer_id      uuid NOT NULL REFERENCES benutzer(id) ON DELETE CASCADE,
    app              text NOT NULL,
    schluessel_hash  text NOT NULL UNIQUE,
    aktiv            boolean NOT NULL DEFAULT true,
    erstellt_am      timestamptz NOT NULL DEFAULT now(),
    zuletzt_genutzt  timestamptz
);

CREATE UNIQUE INDEX IF NOT EXISTS app_zugang_app_idx ON app_zugang (benutzer_id, lower(app));

CREATE TABLE IF NOT EXISTS app_recht (
    zugang_id  uuid NOT NULL REFERENCES app_zugang(id) ON DELETE CASCADE,
    knoten_id  uuid NOT NULL REFERENCES knoten(id) ON DELETE CASCADE,
    recht      text NOT NULL CHECK (recht IN ('lesen', 'schreiben')),
    PRIMARY KEY (zugang_id, knoten_id)
);

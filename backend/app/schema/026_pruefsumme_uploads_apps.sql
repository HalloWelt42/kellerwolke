-- Prüfsumme je Version (KW-11): version.inhalt_hash ist der sha256 des ganzen Inhalts (heute genau ein Block je
-- Version, dessen Name dieser Hash ist). Der Index beantwortet "gibt es diesen Inhalt schon?", ohne Dateien zu lesen.
CREATE INDEX IF NOT EXISTS version_inhalt_hash_idx ON version (inhalt_hash);

-- Fortsetzbare Uploads auch für Apps (KW-11): ein Upload gehört dem, der ihn begonnen hat, der Anmeldung (zugang_id
-- NULL) oder genau einer App. Die Bedingung für eine vorhandene Datei (If-Match-Stand oder nur neu anlegen) wird beim
-- Anlegen genannt und beim Eintragen mit dem letzten Teil unter Sperre geprüft.
ALTER TABLE upload ADD COLUMN IF NOT EXISTS zugang_id uuid REFERENCES app_zugang(id) ON DELETE CASCADE;
ALTER TABLE upload ADD COLUMN IF NOT EXISTS bedingung_etag text;
ALTER TABLE upload ADD COLUMN IF NOT EXISTS nur_neu boolean NOT NULL DEFAULT false;

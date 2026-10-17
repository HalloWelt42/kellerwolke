-- Journal je Ordner beobachtbar: beim Verschieben steht zusätzlich der alte Elternordner im Eintrag, damit auch der
-- Ordner, aus dem etwas herausverschoben wurde, die Änderung sieht. Index für das Aufräumen alter Einträge.

ALTER TABLE aenderung ADD COLUMN IF NOT EXISTS von_parent_id uuid;

CREATE INDEX IF NOT EXISTS aenderung_zeit_idx ON aenderung (zeit);

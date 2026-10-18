-- Optionen einer Anfrage (18.10.2026): wer eine Anfrage an eine andere App weitergibt, darf ihr kleine Angaben
-- mitgeben, etwa die Sprache eines Tons ({"sprache": "en"}). Die angefragte App liest sie beim Abholen; die
-- Kellerwolke deutet sie nicht. Leer heißt: wie die App es von sich aus macht.

ALTER TABLE anfrage ADD COLUMN IF NOT EXISTS optionen jsonb NOT NULL DEFAULT '{}'::jsonb;

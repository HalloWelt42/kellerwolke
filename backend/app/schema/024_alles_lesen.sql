-- Alles lesen (KW-3, 06.11.2026): ein App-Zugang darf auf Wunsch jede Datei seines Kontos lesen, etwa der
-- Assistent, der in der ganzen Wolke sucht. Schreiben bleibt bei den Rechten je Ordner; die Wurzel bekommt kein Recht.
-- Ein Schalter je Zugang in Einstellungen, Zugänge; aus heißt: nur die Ordner der Rechte.

ALTER TABLE app_zugang ADD COLUMN IF NOT EXISTS alles_lesen boolean NOT NULL DEFAULT false;

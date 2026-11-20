-- Verweise (KW-10, 20.11.2026): ein Eintrag, der auf eine Datei desselben Kontos zeigt, statt sie zu kopieren. Jede
-- Datei gibt es so genau einmal; ein Ordner einer App (etwa Apps/Telegram) zeigt auf das Original in einem anderen
-- Ordner (etwa die Bildablage). Regeln in module/speicher/verweise.py:
-- - ziel_id nennt immer das Original (eine Datei); Ketten werden beim Anlegen aufgelöst.
-- - Lesen folgt dem Ziel; ein Verweis hat keine eigenen Versionen und belegt keinen Platz.
-- - Fehlt das Ziel (endgültig gelöscht: ziel_id wird NULL) oder liegt es im Papierkorb, ist der Verweis verwaist.
-- - Das Original nimmt seine Verweise mit in den Papierkorb (gleiche geloescht_wurzel) und holt sie zurück.

ALTER TABLE knoten ADD COLUMN IF NOT EXISTS ziel_id uuid REFERENCES knoten(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS knoten_ziel_idx ON knoten (ziel_id) WHERE ziel_id IS NOT NULL;

DO $$
BEGIN
    ALTER TABLE knoten ADD CONSTRAINT knoten_ziel_nur_verweis CHECK (ziel_id IS NULL OR typ = 'verweis');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

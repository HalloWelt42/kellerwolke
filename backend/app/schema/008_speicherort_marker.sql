-- Volume-Marker des Objekt-Pools. Eine zufaellige UUID, die zugleich in einer
-- Marker-Datei (.kellerwolke_pool) am Pool-Wurzelverzeichnis liegt. Stimmt die
-- Datei mit diesem Wert ueberein, ist bewiesen, dass das RICHTIGE Laufwerk
-- gemountet ist - sonst (abgehaengter Mountpoint = leeres Verzeichnis auf der
-- Systemplatte) wird gar nicht geschrieben, statt still auf die falsche Platte.

ALTER TABLE speicherort ADD COLUMN IF NOT EXISTS marker text;

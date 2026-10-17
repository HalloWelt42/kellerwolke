-- Löschen markiert den ganzen Teilbaum, nicht nur den obersten Knoten. geloescht_wurzel nennt den Knoten, mit dessen
-- Löschen ein Knoten in den Papierkorb kam: der Papierkorb zeigt nur die Wurzeln, Wiederherstellen holt genau den
-- Teilbaum dieser Wurzel zurück. Was vorher schon einzeln gelöscht war, behält seine eigene Wurzel.

ALTER TABLE knoten ADD COLUMN IF NOT EXISTS geloescht_wurzel uuid;

-- Bestand: bisher gelöschte Knoten sind ihre eigene Wurzel.
UPDATE knoten SET geloescht_wurzel = id WHERE geloescht AND geloescht_wurzel IS NULL;

-- Bestand: lebende Knoten unter einem gelöschten Ordner gehören zu dessen Teilbaum (danach gibt es keine mehr).
WITH RECURSIVE unter AS (
    SELECT k.id, w.id AS wurzel FROM knoten k JOIN knoten w ON k.parent_id = w.id
    WHERE w.geloescht AND w.geloescht_wurzel = w.id AND NOT k.geloescht
    UNION ALL
    SELECT k.id, u.wurzel FROM knoten k JOIN unter u ON k.parent_id = u.id WHERE NOT k.geloescht
)
UPDATE knoten SET geloescht = true, geloescht_wurzel = unter.wurzel FROM unter WHERE knoten.id = unter.id;

CREATE INDEX IF NOT EXISTS knoten_papierkorb_idx ON knoten (besitzer_id) WHERE geloescht AND geloescht_wurzel = id;

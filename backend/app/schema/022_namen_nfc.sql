-- Namen in einer Form (Unicode NFC, siehe app/namen.py). Zerlegt gespeicherte Namen (NFD, von macOS) werden
-- umgestellt. Gibt es im selben Ordner schon einen lebenden gleichen Namen, bekommt der spätere eine Zahl
-- ("Runde (2).wav"); gelöscht wird nichts. Wiederholt ausgeführt ändert sich nichts mehr.
DO $$
DECLARE
  r record;
  neu text;
  stamm text;
  endung text;
  n int;
BEGIN
  FOR r IN SELECT id, besitzer_id, parent_id, name, geloescht FROM knoten
           WHERE name <> normalize(name, NFC) ORDER BY erstellt_am, id LOOP
    neu := normalize(r.name, NFC);
    stamm := regexp_replace(neu, '(\.[^./]{1,10})$', '');
    endung := substring(neu from length(stamm) + 1);
    n := 1;
    WHILE NOT r.geloescht AND EXISTS (
      SELECT 1 FROM knoten k WHERE k.besitzer_id = r.besitzer_id AND k.parent_id IS NOT DISTINCT FROM r.parent_id
        AND lower(k.name) = lower(neu) AND NOT k.geloescht AND k.id <> r.id) LOOP
      n := n + 1;
      neu := stamm || ' (' || n || ')' || endung;
    END LOOP;
    UPDATE knoten SET name = neu WHERE id = r.id;
  END LOOP;
END $$;

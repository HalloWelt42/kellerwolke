-- Das Plugin-System ist entfallen, die Medien gehören zum Kern. Weg mit der Verwaltungstabelle und den eigenen
-- Schemata der früheren Plugins (sie hielten nur eine nie benutzte Voreinstellung).

DROP TABLE IF EXISTS plugin;

DO $$
DECLARE s text;
BEGIN
    FOR s IN SELECT nspname FROM pg_namespace WHERE nspname LIKE 'plugin\_%' LOOP
        EXECUTE format('DROP SCHEMA %I CASCADE', s);
    END LOOP;
END $$;

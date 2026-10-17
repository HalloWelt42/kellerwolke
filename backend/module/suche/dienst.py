"""Volltextsuche ueber PostgreSQL (tsvector, deutsche Konfiguration).

Findet Namen (am Knoten selbst) und den Inhalt (sofern extrahierbar). Die Suche ist streng
pro Nutzer gefiltert - niemand findet fremde Inhalte. Nutzereingaben laufen ueber
websearch_to_tsquery (robust, kein Syntaxfehler bei beliebiger Eingabe) und sind
durchgaengig parametrisiert (keine SQL-Injektion).
"""

from psycopg.rows import dict_row

from app.adapters.postgres_metadata import PostgresMetadataRepository

from module.suche.extraktion import inhalt_noetig, text_extrahieren


class SuchDienst:
    def __init__(self, pool) -> None:
        self.pool = pool

    def braucht_inhalt(self, name: str, groesse: int) -> bool:
        """Ob der Inhalt fuer die Indexierung ueberhaupt gelesen werden muss.
        Der Aufrufer kann so eine grosse Datei ungelesen lassen, statt sie fuer
        nichts in den Speicher zu holen."""
        return inhalt_noetig(name, groesse)

    async def indexieren(self, besitzer_id, knoten_id, name, daten) -> None:
        # besitzer_id kommt aus dem Knoten selbst, und es wird nur indexiert,
        # wenn der Knoten dem angegebenen Nutzer gehoert. So kann der Eigentuemer-
        # Stempel nicht vergiftet oder umgestempelt werden (Isolation). Der Name
        # braucht keinen Index-Eintrag: er steht am Knoten selbst (name_tsv).
        inhalt = text_extrahieren(name, daten)
        async with self.pool.connection() as conn:
            async with conn.transaction():
                await conn.execute(
                    "INSERT INTO such_index (knoten_id, besitzer_id, inhalt_tsv) "
                    "SELECT k.id, k.besitzer_id, to_tsvector('german', %s) "
                    "FROM knoten k WHERE k.id = %s AND k.besitzer_id = %s "
                    "ON CONFLICT (knoten_id) DO UPDATE SET inhalt_tsv = EXCLUDED.inhalt_tsv",
                    (inhalt, knoten_id, besitzer_id),
                )

    async def suchen(self, besitzer_id, anfrage, grenze: int = 50):
        """Treffer im Namen (Dateien und Ordner) oder im Inhalt, Name höher gewichtet; mit denselben Zusatzfeldern
        wie die Ordnerliste (Favorit, geteilt, Kinderzahl), dazu Ort (Ordnerkette) und ob der Name traf. Beide
        Teilmengen kommen über ihren eigenen Index."""
        async with self.pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    "WITH q AS (SELECT websearch_to_tsquery('german', %s) AS q), "
                    "treffer AS ("
                    "  SELECT k.id FROM knoten k, q WHERE k.besitzer_id = %s AND NOT k.geloescht AND k.name_tsv @@ q.q "
                    "  UNION "
                    "  SELECT s.knoten_id FROM such_index s, q WHERE s.besitzer_id = %s AND s.inhalt_tsv @@ q.q"
                    ") "
                    "SELECT k.*, v.groesse, "
                    "(SELECT count(*) FROM knoten c WHERE c.parent_id = k.id AND NOT c.geloescht) AS kinder_anzahl, "
                    "EXISTS(SELECT 1 FROM favorit f WHERE f.benutzer_id = k.besitzer_id AND f.knoten_id = k.id) AS favorit, "
                    "EXISTS(SELECT 1 FROM freigabe fr WHERE fr.knoten_id = k.id) AS geteilt, "
                    "k.name_tsv @@ q.q AS im_namen "
                    "FROM treffer t CROSS JOIN q "
                    # Doppelter Eigentuemer-Filter als Defense-in-depth.
                    "JOIN knoten k ON k.id = t.id AND k.besitzer_id = %s AND NOT k.geloescht "
                    "LEFT JOIN such_index s ON s.knoten_id = k.id "
                    "LEFT JOIN version v ON v.id = k.aktuelle_version_id "
                    "ORDER BY (ts_rank(k.name_tsv, q.q) * 4 + coalesce(ts_rank(s.inhalt_tsv, q.q), 0)) DESC, "
                    "         k.geaendert_am DESC "
                    "LIMIT %s",
                    (anfrage, besitzer_id, besitzer_id, besitzer_id, grenze),
                )
                treffer = await cur.fetchall()
            # Ort je Treffer: die Ordnerkette darüber (wenige Treffer, je eine kurze Abfrage).
            repo = PostgresMetadataRepository(conn)
            for t in treffer:
                t["ort"] = await repo.pfad_namen(t["parent_id"]) if t["parent_id"] else []
            return treffer

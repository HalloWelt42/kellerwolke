"""Volltextsuche ueber PostgreSQL (tsvector, deutsche Konfiguration).

Indexiert Name und (sofern extrahierbar) Inhalt je Knoten. Die Suche ist streng
pro Nutzer gefiltert - niemand findet fremde Inhalte. Nutzereingaben laufen ueber
websearch_to_tsquery (robust, kein Syntaxfehler bei beliebiger Eingabe) und sind
durchgaengig parametrisiert (keine SQL-Injektion).
"""

import re

from psycopg.rows import dict_row

from module.suche.extraktion import text_extrahieren


def _name_tokens(name: str) -> str:
    # Trennzeichen zu Leerzeichen, damit "rechnung.txt" als 'rechnung' 'txt' indexiert.
    return re.sub(r"[._/\\-]+", " ", name)


class SuchDienst:
    def __init__(self, pool) -> None:
        self.pool = pool

    async def indexieren(self, besitzer_id, knoten_id, name, daten) -> None:
        inhalt = text_extrahieren(name, daten)
        async with self.pool.connection() as conn:
            async with conn.transaction():
                await conn.execute(
                    "INSERT INTO such_index (knoten_id, besitzer_id, name_tsv, inhalt_tsv) "
                    "VALUES (%s, %s, to_tsvector('german', %s), to_tsvector('german', %s)) "
                    "ON CONFLICT (knoten_id) DO UPDATE SET "
                    "besitzer_id = EXCLUDED.besitzer_id, "
                    "name_tsv = EXCLUDED.name_tsv, "
                    "inhalt_tsv = EXCLUDED.inhalt_tsv",
                    (knoten_id, besitzer_id, _name_tokens(name), inhalt),
                )

    async def suchen(self, besitzer_id, anfrage, grenze: int = 50):
        async with self.pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    "SELECT k.* FROM such_index s JOIN knoten k ON k.id = s.knoten_id "
                    "WHERE s.besitzer_id = %s AND NOT k.geloescht "
                    "AND (s.name_tsv @@ websearch_to_tsquery('german', %s) "
                    "     OR s.inhalt_tsv @@ websearch_to_tsquery('german', %s)) "
                    "ORDER BY ts_rank(s.inhalt_tsv, websearch_to_tsquery('german', %s)) DESC, "
                    "         k.geaendert_am DESC "
                    "LIMIT %s",
                    (besitzer_id, anfrage, anfrage, anfrage, grenze),
                )
                return await cur.fetchall()

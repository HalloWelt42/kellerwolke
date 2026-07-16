"""Volltextsuche ueber PostgreSQL (tsvector, deutsche Konfiguration).

Indexiert Name und (sofern extrahierbar) Inhalt je Knoten. Die Suche ist streng
pro Nutzer gefiltert - niemand findet fremde Inhalte. Nutzereingaben laufen ueber
websearch_to_tsquery (robust, kein Syntaxfehler bei beliebiger Eingabe) und sind
durchgaengig parametrisiert (keine SQL-Injektion).
"""

import re

from psycopg.rows import dict_row

from module.suche.extraktion import inhalt_noetig, text_extrahieren


def _name_tokens(name: str) -> str:
    # Trennzeichen zu Leerzeichen, damit "rechnung.txt" als 'rechnung' 'txt' indexiert.
    # NUL-Bytes entfernen - PostgreSQL-Textfelder lehnen sie ab (wie beim Inhalt).
    return re.sub(r"[._/\\-]+", " ", name).replace("\x00", " ")


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
        # Stempel nicht vergiftet oder umgestempelt werden (Isolation).
        inhalt = text_extrahieren(name, daten)
        async with self.pool.connection() as conn:
            async with conn.transaction():
                await conn.execute(
                    "INSERT INTO such_index (knoten_id, besitzer_id, name_tsv, inhalt_tsv) "
                    "SELECT k.id, k.besitzer_id, to_tsvector('german', %s), "
                    "       to_tsvector('german', %s) "
                    "FROM knoten k WHERE k.id = %s AND k.besitzer_id = %s "
                    "ON CONFLICT (knoten_id) DO UPDATE SET "
                    "name_tsv = EXCLUDED.name_tsv, inhalt_tsv = EXCLUDED.inhalt_tsv",
                    (_name_tokens(name), inhalt, knoten_id, besitzer_id),
                )

    async def suchen(self, besitzer_id, anfrage, grenze: int = 50):
        async with self.pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    "SELECT k.*, v.groesse FROM such_index s "
                    "JOIN knoten k ON k.id = s.knoten_id "
                    "LEFT JOIN version v ON v.id = k.aktuelle_version_id "
                    # Doppelter Eigentuemer-Filter (s und k) als Defense-in-depth.
                    "WHERE s.besitzer_id = %s AND k.besitzer_id = %s AND NOT k.geloescht "
                    "AND (s.name_tsv @@ websearch_to_tsquery('german', %s) "
                    "     OR s.inhalt_tsv @@ websearch_to_tsquery('german', %s)) "
                    # Namens- und Inhaltsrang kombiniert, Name hoeher gewichtet.
                    "ORDER BY (ts_rank(s.name_tsv, websearch_to_tsquery('german', %s)) * 4 "
                    "          + ts_rank(s.inhalt_tsv, websearch_to_tsquery('german', %s))) DESC, "
                    "         k.geaendert_am DESC "
                    "LIMIT %s",
                    (besitzer_id, besitzer_id, anfrage, anfrage, anfrage, anfrage, grenze),
                )
                return await cur.fetchall()

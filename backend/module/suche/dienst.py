"""Volltextsuche ueber PostgreSQL (tsvector, deutsche Konfiguration).

Findet Namen (am Knoten selbst) und den Inhalt (sofern extrahierbar). Die Suche ist streng
pro Nutzer gefiltert - niemand findet fremde Inhalte. Nutzereingaben laufen ueber
websearch_to_tsquery (robust, kein Syntaxfehler bei beliebiger Eingabe) und sind
durchgaengig parametrisiert (keine SQL-Injektion).
"""

import asyncio
from io import BytesIO

from psycopg.rows import dict_row

from app.adapters.postgres_metadata import PostgresMetadataRepository

from module.suche.extraktion import inhalt_noetig, lesemenge, text_extrahieren


def indizierung_starten(vorgaenge, suche, speicher, besitzer_id, knoten) -> None:
    """Den Suchindex einer Datei als Hintergrund-Vorgang nachziehen: das Schreiben wartet nicht darauf, und ein
    Index-Fehler lässt es nicht scheitern. Ein Weg für Browser, Apps und WebDAV."""

    async def _arbeit(_vorgang):
        await suche.datei_indexieren(speicher, besitzer_id, knoten["id"])

    vorgaenge.starte(besitzer_id, "indizierung", f"{knoten['name']} indizieren", _arbeit)


class SuchDienst:
    def __init__(self, pool) -> None:
        self.pool = pool

    async def datei_indexieren(self, speicher, besitzer_id, knoten_id) -> None:
        """Den Inhalt einer eigenen Datei in den Index nehmen, im aktuellen Stand. Gelesen wird nur, was die Extraktion
        braucht, und zwar aus dem Pfad des Blocks; das Zerlegen (PDF, docx) läuft in einem Faden, die Ereignisschleife
        bleibt frei. Fremde oder verschwundene Dateien bleiben unberührt (Isolation)."""
        stand = await speicher.eigene_datei(besitzer_id, knoten_id)
        if stand is None:
            return
        name = stand.knoten["name"]
        text = await self._text(speicher, stand, name) if inhalt_noetig(name, stand.groesse) else ""
        await self.inhalt_speichern(besitzer_id, knoten_id, text)

    async def _text(self, speicher, stand, name: str) -> str:
        pfad = await speicher.stand_pfad(stand)
        if pfad:
            return await asyncio.to_thread(_aus_datei, name, pfad)
        # Ohne Pfad (mehrere Blöcke): nur so viel holen, wie die Art braucht.
        daten = b"".join([b async for b in speicher.stand_stroemen(stand, 0, lesemenge(name))])
        return await asyncio.to_thread(text_extrahieren, name, BytesIO(daten))

    async def inhalt_speichern(self, besitzer_id, knoten_id, text: str) -> None:
        # besitzer_id kommt aus dem Knoten selbst, und es wird nur indexiert,
        # wenn der Knoten dem angegebenen Nutzer gehoert. So kann der Eigentuemer-
        # Stempel nicht vergiftet oder umgestempelt werden (Isolation). Der Name
        # braucht keinen Index-Eintrag: er steht am Knoten selbst (name_tsv).
        async with self.pool.connection() as conn:
            async with conn.transaction():
                await conn.execute(
                    "INSERT INTO such_index (knoten_id, besitzer_id, inhalt_tsv) "
                    "SELECT k.id, k.besitzer_id, to_tsvector('german', %s) "
                    "FROM knoten k WHERE k.id = %s AND k.besitzer_id = %s "
                    "ON CONFLICT (knoten_id) DO UPDATE SET inhalt_tsv = EXCLUDED.inhalt_tsv",
                    (text, knoten_id, besitzer_id),
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


def _aus_datei(name: str, pfad) -> str:
    with open(pfad, "rb") as datei:
        return text_extrahieren(name, datei)

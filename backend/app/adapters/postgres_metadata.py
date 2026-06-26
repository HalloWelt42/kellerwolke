"""PostgreSQL-Adapter fuer die Metadaten (Knoten, Versionen, Chunks, Blob-Refcount,
Journal). Arbeitet auf einer uebergebenen Verbindung, damit der SpeicherDienst
mehrere Schreibvorgaenge in einer Transaktion buendeln kann.
"""

from psycopg.rows import dict_row


class PostgresMetadataRepository:
    def __init__(self, conn) -> None:
        self.conn = conn

    async def _eine(self, sql, params=()):
        async with self.conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(sql, params)
            return await cur.fetchone()

    async def _alle(self, sql, params=()):
        async with self.conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(sql, params)
            return await cur.fetchall()

    # --- Konten ---------------------------------------------------------------

    async def benutzer_anlegen(self, name, passwort_hash=None, rolle="mitglied"):
        return await self._eine(
            "INSERT INTO benutzer (name, passwort_hash, rolle) VALUES (%s,%s,%s) RETURNING *",
            (name, passwort_hash, rolle),
        )

    # --- Knoten ---------------------------------------------------------------

    async def ordner_anlegen(self, besitzer_id, parent_id, name):
        return await self._eine(
            "INSERT INTO knoten (besitzer_id, parent_id, name, typ) "
            "VALUES (%s,%s,%s,'ordner') RETURNING *",
            (besitzer_id, parent_id, name),
        )

    async def datei_anlegen(self, besitzer_id, parent_id, name):
        return await self._eine(
            "INSERT INTO knoten (besitzer_id, parent_id, name, typ) "
            "VALUES (%s,%s,%s,'datei') RETURNING *",
            (besitzer_id, parent_id, name),
        )

    async def datei_upsert(self, besitzer_id, parent_id, name):
        """Legt den Datei-Knoten an oder findet den vorhandenen - atomar, ohne
        Check-then-act-Race. Liefert die Zeile inkl. Feld 'eingefuegt' (True,
        wenn neu angelegt)."""
        return await self._eine(
            "INSERT INTO knoten (besitzer_id, parent_id, name, typ) "
            "VALUES (%s,%s,%s,'datei') "
            "ON CONFLICT (besitzer_id, parent_id, lower(name)) WHERE NOT geloescht "
            "DO UPDATE SET geaendert_am = now() "
            "RETURNING *, (xmax = 0) AS eingefuegt",
            (besitzer_id, parent_id, name),
        )

    async def extern_anlegen(self, besitzer_id, parent_id, name, extern_pfad):
        return await self._eine(
            "INSERT INTO knoten (besitzer_id, parent_id, name, typ, extern_pfad) "
            "VALUES (%s,%s,%s,'extern',%s) RETURNING *",
            (besitzer_id, parent_id, name, extern_pfad),
        )

    async def knoten_holen(self, knoten_id):
        return await self._eine("SELECT * FROM knoten WHERE id=%s", (knoten_id,))

    async def knoten_finden(self, besitzer_id, parent_id, name):
        if parent_id is None:
            return await self._eine(
                "SELECT * FROM knoten WHERE besitzer_id=%s AND parent_id IS NULL "
                "AND lower(name)=lower(%s) AND NOT geloescht",
                (besitzer_id, name),
            )
        return await self._eine(
            "SELECT * FROM knoten WHERE besitzer_id=%s AND parent_id=%s "
            "AND lower(name)=lower(%s) AND NOT geloescht",
            (besitzer_id, parent_id, name),
        )

    async def kinder(self, besitzer_id, parent_id):
        # Groesse der aktuellen Version gleich mitliefern (LEFT JOIN, hoechstens
        # ein Treffer je Knoten), damit die Liste sie ohne Zusatzabfrage zeigt.
        if parent_id is None:
            return await self._alle(
                "SELECT k.*, v.groesse FROM knoten k "
                "LEFT JOIN version v ON v.id = k.aktuelle_version_id "
                "WHERE k.besitzer_id=%s AND k.parent_id IS NULL "
                "AND NOT k.geloescht ORDER BY k.typ, lower(k.name)",
                (besitzer_id,),
            )
        return await self._alle(
            "SELECT k.*, v.groesse FROM knoten k "
            "LEFT JOIN version v ON v.id = k.aktuelle_version_id "
            "WHERE k.besitzer_id=%s AND k.parent_id=%s "
            "AND NOT k.geloescht ORDER BY k.typ, lower(k.name)",
            (besitzer_id, parent_id),
        )

    async def knoten_setzen_version(self, knoten_id, version_id, etag):
        await self.conn.execute(
            "UPDATE knoten SET aktuelle_version_id=%s, etag=%s, geaendert_am=now() WHERE id=%s",
            (version_id, etag, knoten_id),
        )

    async def knoten_umbenennen(self, besitzer_id, knoten_id, neuer_name):
        await self.conn.execute(
            "UPDATE knoten SET name=%s, geaendert_am=now() WHERE id=%s AND besitzer_id=%s",
            (neuer_name, knoten_id, besitzer_id),
        )

    async def knoten_verschieben(self, besitzer_id, knoten_id, neuer_parent):
        await self.conn.execute(
            "UPDATE knoten SET parent_id=%s, geaendert_am=now() WHERE id=%s AND besitzer_id=%s",
            (neuer_parent, knoten_id, besitzer_id),
        )

    async def knoten_loeschen(self, besitzer_id, knoten_id):
        await self.conn.execute(
            "UPDATE knoten SET geloescht=true, geaendert_am=now() WHERE id=%s AND besitzer_id=%s",
            (knoten_id, besitzer_id),
        )

    async def knoten_wiederherstellen(self, besitzer_id, knoten_id, name):
        await self.conn.execute(
            "UPDATE knoten SET geloescht=false, name=%s, geaendert_am=now() "
            "WHERE id=%s AND besitzer_id=%s",
            (name, knoten_id, besitzer_id),
        )

    async def papierkorb(self, besitzer_id):
        return await self._alle(
            "SELECT k.*, v.groesse FROM knoten k "
            "LEFT JOIN version v ON v.id = k.aktuelle_version_id "
            "WHERE k.besitzer_id=%s AND k.geloescht "
            "ORDER BY k.geaendert_am DESC",
            (besitzer_id,),
        )

    async def ist_im_teilbaum(self, wurzel_id, kandidat_id) -> bool:
        """True, wenn kandidat_id der Knoten wurzel_id selbst oder ein Nachkomme
        davon ist (zum Erkennen von Verschiebe-Zyklen)."""
        row = await self._eine(
            "WITH RECURSIVE kette AS ("
            "  SELECT id FROM knoten WHERE id=%s "
            "  UNION ALL "
            "  SELECT k.id FROM knoten k JOIN kette ON k.parent_id = kette.id"
            ") SELECT 1 FROM kette WHERE id=%s LIMIT 1",
            (wurzel_id, kandidat_id),
        )
        return row is not None

    # --- Versionen und Chunks -------------------------------------------------

    async def version_anlegen(self, knoten_id, groesse, inhalt_hash, erstellt_von):
        return await self._eine(
            "INSERT INTO version (knoten_id, groesse, inhalt_hash, erstellt_von) "
            "VALUES (%s,%s,%s,%s) RETURNING *",
            (knoten_id, groesse, inhalt_hash, erstellt_von),
        )

    async def version_holen(self, version_id):
        return await self._eine("SELECT * FROM version WHERE id=%s", (version_id,))

    async def versionen(self, knoten_id):
        # seq ist monoton und eindeutig -> stabile Ordnung auch bei gleichem Zeitstempel.
        return await self._alle(
            "SELECT * FROM version WHERE knoten_id=%s ORDER BY seq DESC",
            (knoten_id,),
        )

    async def chunk_anlegen(self, version_id, reihenfolge, blob_hash, groesse):
        await self.conn.execute(
            "INSERT INTO chunk (version_id, reihenfolge, blob_hash, groesse) "
            "VALUES (%s,%s,%s,%s)",
            (version_id, reihenfolge, blob_hash, groesse),
        )

    async def chunks(self, version_id):
        return await self._alle(
            "SELECT * FROM chunk WHERE version_id=%s ORDER BY reihenfolge",
            (version_id,),
        )

    # --- Blob-Refcount (Dedup pro Nutzer) -------------------------------------

    async def blob_erhoehen(self, besitzer_id, blob_hash, groesse):
        row = await self._eine(
            "INSERT INTO blob (besitzer_id, hash, groesse, refcount) VALUES (%s,%s,%s,1) "
            "ON CONFLICT (besitzer_id, hash) DO UPDATE SET refcount = blob.refcount + 1 "
            "RETURNING refcount",
            (besitzer_id, blob_hash, groesse),
        )
        return row["refcount"]

    async def blob_holen(self, besitzer_id, blob_hash):
        return await self._eine(
            "SELECT * FROM blob WHERE besitzer_id=%s AND hash=%s",
            (besitzer_id, blob_hash),
        )

    # --- Journal (Sync-Vorbereitung) ------------------------------------------

    async def journal_anhaengen(self, besitzer_id, knoten_id, typ, version_id=None):
        row = await self._eine(
            "INSERT INTO aenderung (besitzer_id, knoten_id, typ, version_id) "
            "VALUES (%s,%s,%s,%s) RETURNING seq",
            (besitzer_id, knoten_id, typ, version_id),
        )
        return row["seq"]

    async def journal_seit(self, besitzer_id, seit_seq):
        return await self._alle(
            "SELECT * FROM aenderung WHERE besitzer_id=%s AND seq > %s ORDER BY seq",
            (besitzer_id, seit_seq),
        )

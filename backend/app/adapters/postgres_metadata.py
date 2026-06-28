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
        # Zusaetzlich die Kinderzahl je Ordner (Zaehler) und Favoriten-Markierung.
        zusatz = (
            "(SELECT count(*) FROM knoten c "
            "WHERE c.parent_id = k.id AND NOT c.geloescht) AS kinder_anzahl, "
            "EXISTS(SELECT 1 FROM favorit f "
            "WHERE f.benutzer_id = k.besitzer_id AND f.knoten_id = k.id) AS favorit"
        )
        if parent_id is None:
            return await self._alle(
                f"SELECT k.*, v.groesse, {zusatz} FROM knoten k "
                "LEFT JOIN version v ON v.id = k.aktuelle_version_id "
                "WHERE k.besitzer_id=%s AND k.parent_id IS NULL "
                "AND NOT k.geloescht "
                "ORDER BY CASE k.typ WHEN 'ordner' THEN 0 WHEN 'extern' THEN 1 ELSE 2 END, "
                "lower(k.name)",
                (besitzer_id,),
            )
        return await self._alle(
            f"SELECT k.*, v.groesse, {zusatz} FROM knoten k "
            "LEFT JOIN version v ON v.id = k.aktuelle_version_id "
            "WHERE k.besitzer_id=%s AND k.parent_id=%s "
            "AND NOT k.geloescht "
            "ORDER BY CASE k.typ WHEN 'ordner' THEN 0 WHEN 'extern' THEN 1 ELSE 2 END, "
            "lower(k.name)",
            (besitzer_id, parent_id),
        )

    async def favoriten(self, besitzer_id):
        return await self._alle(
            "SELECT k.*, v.groesse, true AS favorit, "
            "(SELECT count(*) FROM knoten c WHERE c.parent_id = k.id AND NOT c.geloescht) "
            "AS kinder_anzahl "
            "FROM favorit f JOIN knoten k ON k.id = f.knoten_id "
            "LEFT JOIN version v ON v.id = k.aktuelle_version_id "
            "WHERE f.benutzer_id=%s AND NOT k.geloescht "
            "ORDER BY CASE k.typ WHEN 'ordner' THEN 0 WHEN 'extern' THEN 1 ELSE 2 END, "
            "lower(k.name)",
            (besitzer_id,),
        )

    async def favorit_setzen(self, besitzer_id, knoten_id):
        await self.conn.execute(
            "INSERT INTO favorit (benutzer_id, knoten_id) VALUES (%s, %s) "
            "ON CONFLICT DO NOTHING",
            (besitzer_id, knoten_id),
        )

    async def favorit_entfernen(self, besitzer_id, knoten_id):
        await self.conn.execute(
            "DELETE FROM favorit WHERE benutzer_id=%s AND knoten_id=%s",
            (besitzer_id, knoten_id),
        )

    # --- Freigaben (intern: an ein Konto) ------------------------------------

    async def freigabe_setzen(self, knoten_id, ziel_id, rechte):
        await self.conn.execute(
            "DELETE FROM freigabe WHERE typ='intern' AND knoten_id=%s AND ziel_benutzer_id=%s",
            (knoten_id, ziel_id),
        )
        await self.conn.execute(
            "INSERT INTO freigabe (knoten_id, typ, ziel_benutzer_id, rechte) "
            "VALUES (%s, 'intern', %s, %s)",
            (knoten_id, ziel_id, rechte),
        )

    async def freigabe_entfernen(self, knoten_id, ziel_id):
        await self.conn.execute(
            "DELETE FROM freigabe WHERE typ='intern' AND knoten_id=%s AND ziel_benutzer_id=%s",
            (knoten_id, ziel_id),
        )

    async def freigaben(self, knoten_id):
        return await self._alle(
            "SELECT f.ziel_benutzer_id, f.rechte, b.name AS ziel_name "
            "FROM freigabe f JOIN benutzer b ON b.id = f.ziel_benutzer_id "
            "WHERE f.typ='intern' AND f.knoten_id=%s ORDER BY lower(b.name)",
            (knoten_id,),
        )

    async def geteilt_mit(self, benutzer_id):
        """Knoten, die DIREKT an benutzer_id freigegeben sind (mit Eigentuemer-Name)."""
        return await self._alle(
            "SELECT k.*, v.groesse, ob.name AS besitzer_name, "
            "(SELECT count(*) FROM knoten c WHERE c.parent_id=k.id AND NOT c.geloescht) "
            "AS kinder_anzahl "
            "FROM freigabe f "
            "JOIN knoten k ON k.id = f.knoten_id "
            "JOIN benutzer ob ON ob.id = k.besitzer_id "
            "LEFT JOIN version v ON v.id = k.aktuelle_version_id "
            "WHERE f.typ='intern' AND f.ziel_benutzer_id=%s AND NOT k.geloescht "
            "ORDER BY CASE k.typ WHEN 'ordner' THEN 0 WHEN 'extern' THEN 1 ELSE 2 END, "
            "lower(k.name)",
            (benutzer_id,),
        )

    async def lese_zugriff(self, benutzer_id, knoten_id) -> bool:
        """True, wenn benutzer den Knoten lesen darf: Eigentuemer ODER der Knoten
        selbst bzw. ein Vorfahr ist intern an benutzer freigegeben."""
        treffer = await self._eine(
            "WITH RECURSIVE kette AS ("
            "  SELECT id, parent_id, besitzer_id FROM knoten WHERE id=%s "
            "  UNION ALL "
            "  SELECT k.id, k.parent_id, k.besitzer_id FROM knoten k "
            "  JOIN kette ON k.id = kette.parent_id"
            ") "
            "SELECT 1 FROM kette WHERE besitzer_id=%s "
            "UNION ALL "
            "SELECT 1 FROM freigabe f WHERE f.typ='intern' AND f.ziel_benutzer_id=%s "
            "  AND f.knoten_id IN (SELECT id FROM kette) "
            "LIMIT 1",
            (knoten_id, benutzer_id, benutzer_id),
        )
        return treffer is not None

    async def kinder_nach_parent(self, parent_id):
        """Kinder eines Ordners ohne Eigentuemer-Filter (fuer geteiltes Browsen;
        der Zugriff auf den Ordner ist vorher per lese_zugriff geprueft)."""
        return await self._alle(
            "SELECT k.*, v.groesse, "
            "(SELECT count(*) FROM knoten c WHERE c.parent_id=k.id AND NOT c.geloescht) "
            "AS kinder_anzahl "
            "FROM knoten k LEFT JOIN version v ON v.id = k.aktuelle_version_id "
            "WHERE k.parent_id=%s AND NOT k.geloescht "
            "ORDER BY CASE k.typ WHEN 'ordner' THEN 0 WHEN 'extern' THEN 1 ELSE 2 END, "
            "lower(k.name)",
            (parent_id,),
        )

    async def speicher_status(self, besitzer_id):
        benutzt = await self._eine(
            "SELECT coalesce(sum(groesse), 0) AS s FROM blob "
            "WHERE besitzer_id=%s AND refcount > 0",
            (besitzer_id,),
        )
        konto = await self._eine("SELECT quota_bytes FROM benutzer WHERE id=%s", (besitzer_id,))
        return {
            "benutzt": int(benutzt["s"]) if benutzt else 0,
            "quota": konto["quota_bytes"] if konto else None,
        }

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

    async def speicherort_holen(self):
        return await self._eine("SELECT pfad, marker FROM speicherort WHERE id = 1")

    async def speicherort_setzen(self, pfad, marker=None):
        # marker=None laesst einen bestehenden Marker unangetastet (COALESCE),
        # damit reine Pfad-Updates ihn nicht versehentlich loeschen.
        await self.conn.execute(
            "INSERT INTO speicherort (id, pfad, marker) VALUES (1, %s, %s) "
            "ON CONFLICT (id) DO UPDATE SET pfad = EXCLUDED.pfad, "
            "marker = COALESCE(EXCLUDED.marker, speicherort.marker), geaendert_am = now()",
            (pfad, marker),
        )

    async def papierkorb_wurzeln(self, besitzer_id):
        zeilen = await self._alle(
            "SELECT id FROM knoten WHERE besitzer_id=%s AND geloescht", (besitzer_id,)
        )
        return [z["id"] for z in zeilen]

    async def blobrefs_im_teilbaum(self, wurzeln):
        """Liefert je Blockhash, wie oft er im Teilbaum der Wurzeln referenziert
        wird (ueber Versionen/Chunks). Grundlage fuer das Senken der Refcounts."""
        if not wurzeln:
            return []
        return await self._alle(
            "WITH RECURSIVE baum AS ("
            "  SELECT id FROM knoten WHERE id = ANY(%s) "
            "  UNION ALL "
            "  SELECT k.id FROM knoten k JOIN baum b ON k.parent_id = b.id"
            ") "
            "SELECT c.blob_hash AS hash, count(*) AS n "
            "FROM chunk c JOIN version v ON v.id = c.version_id "
            "WHERE v.knoten_id IN (SELECT id FROM baum) "
            "GROUP BY c.blob_hash",
            (wurzeln,),
        )

    async def blob_refcount_senken(self, besitzer_id, blob_hash, n):
        """Senkt den Refcount und liefert den neuen Wert (oder None, wenn weg)."""
        zeile = await self._eine(
            "UPDATE blob SET refcount = refcount - %s "
            "WHERE besitzer_id=%s AND hash=%s RETURNING refcount",
            (n, besitzer_id, blob_hash),
        )
        return zeile["refcount"] if zeile else None

    async def blob_zeile_loeschen(self, besitzer_id, blob_hash):
        await self.conn.execute(
            "DELETE FROM blob WHERE besitzer_id=%s AND hash=%s AND refcount <= 0",
            (besitzer_id, blob_hash),
        )

    async def knoten_hart_loeschen(self, wurzeln):
        if not wurzeln:
            return
        # ON DELETE CASCADE raeumt Kinder, Versionen und Chunks mit ab.
        await self.conn.execute("DELETE FROM knoten WHERE id = ANY(%s)", (wurzeln,))

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

    async def alle_blobs(self):
        """Soll-Zustand des Pools: jeder Block, den die DB kennt (fuer den
        Konsistenzabgleich mit den physisch vorhandenen Dateien)."""
        return await self._alle("SELECT besitzer_id, hash, groesse FROM blob")

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

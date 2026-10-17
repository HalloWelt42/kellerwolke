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

    async def ordner_lebt(self, besitzer_id, ordner_id) -> bool:
        """True für die Wurzel oder einen lebenden eigenen Ordner. Die Zeile bleibt bis zum Ende der Transaktion
        gegen gleichzeitiges Löschen gesperrt: was hier hineinkommt, landet nie unsichtbar im Papierkorb."""
        if ordner_id is None:
            return True
        zeile = await self._eine(
            "SELECT 1 AS da FROM knoten WHERE id=%s AND besitzer_id=%s AND typ='ordner' AND NOT geloescht FOR SHARE",
            (ordner_id, besitzer_id),
        )
        return zeile is not None

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
        # Zusaetzlich die Kinderzahl je Ordner (Zaehler), Favoriten-Markierung und
        # ob der Knoten mit jemandem geteilt ist (dann Kennzeichen in der Liste).
        zusatz = (
            "(SELECT count(*) FROM knoten c "
            "WHERE c.parent_id = k.id AND NOT c.geloescht) AS kinder_anzahl, "
            "EXISTS(SELECT 1 FROM favorit f "
            "WHERE f.benutzer_id = k.besitzer_id AND f.knoten_id = k.id) AS favorit, "
            "EXISTS(SELECT 1 FROM freigabe fr "
            "WHERE fr.knoten_id = k.id) AS geteilt"
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

    async def alle_dateien(self, besitzer_id, endungen):
        """Alle (nicht geloeschten) Datei-Knoten des Nutzers im GANZEN Baum, je
        Treffer mit vollem Ordnerpfad (Ahnenkette als jsonb-Liste {id,name}),
        optional gefiltert auf Namens-Endungen (LIKE-Muster, klein geschrieben).
        Generische Primitive - z.B. fuer eine zentrale Bild-/Medienansicht.
        Die Rekursion steigt vom Wurzelknoten ab und reicht den Pfad mit."""
        return await self._alle(
            "WITH RECURSIVE baum AS ("
            "  SELECT id, parent_id, name, typ, aktuelle_version_id, geaendert_am, "
            "         '[]'::jsonb AS pfad "
            "  FROM knoten "
            "  WHERE besitzer_id=%s AND parent_id IS NULL AND NOT geloescht "
            "  UNION ALL "
            "  SELECT k.id, k.parent_id, k.name, k.typ, k.aktuelle_version_id, k.geaendert_am, "
            "         b.pfad || jsonb_build_object('id', b.id::text, 'name', b.name) "
            "  FROM knoten k JOIN baum b ON k.parent_id = b.id "
            "  WHERE k.besitzer_id=%s AND NOT k.geloescht"
            ") "
            "SELECT baum.id, baum.name, baum.pfad, baum.geaendert_am, v.groesse "
            "FROM baum LEFT JOIN version v ON v.id = baum.aktuelle_version_id "
            "WHERE baum.typ='datei' AND lower(baum.name) LIKE ANY(%s) "
            "ORDER BY lower(baum.name)",
            (besitzer_id, besitzer_id, list(endungen)),
        )

    async def favoriten(self, besitzer_id):
        return await self._alle(
            "SELECT k.*, v.groesse, true AS favorit, "
            "(SELECT count(*) FROM knoten c WHERE c.parent_id = k.id AND NOT c.geloescht) "
            "AS kinder_anzahl, "
            "EXISTS(SELECT 1 FROM freigabe fr WHERE fr.knoten_id = k.id) AS geteilt "
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
        """Legt den Knoten samt lebendem Teilbaum in den Papierkorb, mit ihm als Wurzel. Schon einzeln Gelöschtes
        darunter behält seine eigene Wurzel. Das Änderungsdatum zeigt bei der Wurzel den Zeitpunkt des Löschens.

        Erst wird der Teilbaum gesperrt: wer gerade hineinschreibt (ordner_lebt), ist danach fertig und steht im
        Stand der zweiten Anweisung; wer später kommt, sieht den Ordner gelöscht."""
        await self.conn.execute(
            "WITH RECURSIVE baum AS ("
            "  SELECT id FROM knoten WHERE id=%s AND besitzer_id=%s "
            "  UNION ALL "
            "  SELECT k.id FROM knoten k JOIN baum b ON k.parent_id = b.id WHERE NOT k.geloescht"
            ") SELECT id FROM knoten WHERE id IN (SELECT id FROM baum) FOR UPDATE",
            (knoten_id, besitzer_id),
        )
        await self.conn.execute(
            "WITH RECURSIVE baum AS ("
            "  SELECT id FROM knoten WHERE id=%s AND besitzer_id=%s AND NOT geloescht "
            "  UNION ALL "
            "  SELECT k.id FROM knoten k JOIN baum b ON k.parent_id = b.id WHERE NOT k.geloescht"
            ") UPDATE knoten SET geloescht=true, geloescht_wurzel=%s, "
            "geaendert_am = CASE WHEN knoten.id=%s THEN now() ELSE knoten.geaendert_am END "
            "WHERE id IN (SELECT id FROM baum)",
            (knoten_id, besitzer_id, knoten_id, knoten_id),
        )

    async def knoten_wiederherstellen(self, besitzer_id, knoten_id, name, parent_id):
        """Holt den Teilbaum einer Papierkorb-Wurzel zurück; die Wurzel selbst unter name in parent_id."""
        await self.conn.execute(
            "UPDATE knoten SET geloescht=false, geloescht_wurzel=NULL "
            "WHERE geloescht_wurzel=%s AND besitzer_id=%s AND id<>%s",
            (knoten_id, besitzer_id, knoten_id),
        )
        await self.conn.execute(
            "UPDATE knoten SET geloescht=false, geloescht_wurzel=NULL, name=%s, parent_id=%s, geaendert_am=now() "
            "WHERE id=%s AND besitzer_id=%s",
            (name, parent_id, knoten_id, besitzer_id),
        )

    async def papierkorb(self, besitzer_id):
        """Nur die Wurzeln: was mit einem Ordner gelöscht wurde, steckt in ihm."""
        return await self._alle(
            "SELECT k.*, v.groesse FROM knoten k "
            "LEFT JOIN version v ON v.id = k.aktuelle_version_id "
            "WHERE k.besitzer_id=%s AND k.geloescht AND k.geloescht_wurzel = k.id "
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
            "SELECT id FROM knoten WHERE besitzer_id=%s AND geloescht AND geloescht_wurzel = id", (besitzer_id,)
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

    async def fremde_sperre(self, knoten_id, zugang_id) -> dict | None:
        """Gültige Bearbeitungssperre einer anderen App auf dem Knoten, sonst None."""
        return await self._eine("SELECT app, grund, seit, bis FROM sperre WHERE knoten_id=%s AND bis > now() "
                                "AND zugang_id <> %s", (knoten_id, zugang_id))

    async def inhaltstyp(self, knoten_id) -> str | None:
        """Gespeicherter Inhaltstyp einer Datei (von der schreibenden App) oder None."""
        zeile = await self._eine("SELECT inhaltstyp FROM datei_meta WHERE knoten_id=%s", (knoten_id,))
        return zeile["inhaltstyp"] if zeile else None

    async def pfad_namen(self, knoten_id) -> list[str]:
        """Namen vom Wurzelordner bis zum Knoten, für Pfadangaben (leer, wenn es den Knoten nicht gibt)."""
        zeilen = await self._alle(
            "WITH RECURSIVE kette AS ("
            "  SELECT id, parent_id, name, 0 AS tiefe FROM knoten WHERE id=%s "
            "  UNION ALL "
            "  SELECT k.id, k.parent_id, k.name, kette.tiefe + 1 FROM knoten k JOIN kette ON k.id = kette.parent_id"
            ") SELECT name FROM kette ORDER BY tiefe DESC",
            (knoten_id,),
        )
        return [z["name"] for z in zeilen]

    async def ahnen(self, knoten_id) -> list[dict]:
        """Ordner über dem Knoten, von der Wurzel abwärts bis zum Elternordner, als {id, name}."""
        zeilen = await self._alle(
            "WITH RECURSIVE kette AS ("
            "  SELECT parent_id, 0 AS tiefe FROM knoten WHERE id=%s "
            "  UNION ALL "
            "  SELECT k.parent_id, kette.tiefe + 1 FROM knoten k JOIN kette ON k.id = kette.parent_id"
            ") SELECT k.id, k.name FROM kette JOIN knoten k ON k.id = kette.parent_id ORDER BY kette.tiefe DESC",
            (knoten_id,),
        )
        return [{"id": str(z["id"]), "name": z["name"]} for z in zeilen]

    async def kinder_seite(self, parent_id, ab: int, anzahl: int):
        """Eine Seite der lebenden Kinder eines Ordners in fester Reihenfolge (Ordner vor Dateien, Name, Kennung),
        mit Größe der aktuellen Version. Der Zugriff auf den Ordner ist vorher geprüft."""
        return await self._alle(
            "SELECT k.*, v.groesse FROM knoten k LEFT JOIN version v ON v.id = k.aktuelle_version_id "
            "WHERE k.parent_id=%s AND NOT k.geloescht "
            "ORDER BY CASE k.typ WHEN 'ordner' THEN 0 WHEN 'extern' THEN 1 ELSE 2 END, lower(k.name), k.id "
            "LIMIT %s OFFSET %s",
            (parent_id, anzahl, ab),
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

    async def alle_blobs(self):
        """Soll-Zustand des Pools: jeder Block, den die DB kennt (fuer den
        Konsistenzabgleich mit den physisch vorhandenen Dateien)."""
        return await self._alle("SELECT besitzer_id, hash, groesse FROM blob")

    # --- Journal (Sync-Vorbereitung) ------------------------------------------

    async def journal_anhaengen(self, besitzer_id, knoten_id, typ, version_id=None, von_parent_id=None):
        """Eintrag ins Journal und Benachrichtigung der Beobachter. NOTIFY wird erst beim Festschreiben der
        Transaktion zugestellt: wer geweckt wird, sieht den Eintrag auch."""
        row = await self._eine(
            "INSERT INTO aenderung (besitzer_id, knoten_id, typ, version_id, von_parent_id) "
            "VALUES (%s,%s,%s,%s,%s) RETURNING seq",
            (besitzer_id, knoten_id, typ, version_id, von_parent_id),
        )
        await self.conn.execute("SELECT pg_notify('kellerwolke_journal', %s)", (str(besitzer_id),))
        return row["seq"]

    async def journal_seit(self, besitzer_id, seit_seq, anzahl: int = 1000):
        return await self._alle(
            "SELECT * FROM aenderung WHERE besitzer_id=%s AND seq > %s ORDER BY seq LIMIT %s",
            (besitzer_id, seit_seq, anzahl),
        )

    async def journal_im_ordner(self, besitzer_id, ordner_id, seit_seq, anzahl: int):
        """Einträge seit seq für alles unter einem Ordner (auch Herausverschobenes über den alten Elternordner)."""
        return await self._alle(
            "WITH RECURSIVE baum AS ("
            "  SELECT id FROM knoten WHERE id=%s "
            "  UNION ALL "
            "  SELECT k.id FROM knoten k JOIN baum ON k.parent_id = baum.id"
            ") SELECT a.seq, a.knoten_id, a.typ, a.version_id, a.von_parent_id, a.zeit FROM aenderung a "
            "WHERE a.besitzer_id=%s AND a.seq > %s "
            "AND (a.knoten_id IN (SELECT id FROM baum) OR a.von_parent_id IN (SELECT id FROM baum)) "
            "ORDER BY a.seq LIMIT %s",
            (ordner_id, besitzer_id, seit_seq, anzahl),
        )

    async def journal_grenzen(self, besitzer_id) -> tuple[int, int]:
        """(kleinste, größte) vorhandene seq des Kontos; (0, 0) ohne Einträge."""
        row = await self._eine("SELECT coalesce(min(seq),0) AS a, coalesce(max(seq),0) AS b FROM aenderung WHERE besitzer_id=%s",
                               (besitzer_id,))
        return row["a"], row["b"]

    async def journal_aufraeumen(self, tage: int) -> int:
        cur = await self.conn.execute("DELETE FROM aenderung WHERE zeit < now() - make_interval(days => %s)", (tage,))
        return cur.rowcount

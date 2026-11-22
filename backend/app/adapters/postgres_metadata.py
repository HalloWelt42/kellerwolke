"""PostgreSQL-Adapter fuer die Metadaten (Knoten, Versionen, Chunks, Blob-Refcount,
Journal). Arbeitet auf einer uebergebenen Verbindung, damit der SpeicherDienst
mehrere Schreibvorgaenge in einer Transaktion buendeln kann.
"""

from psycopg.rows import dict_row

from app.namen import nfc

# Verweise (KW-10): Angaben des Originals an der Zeile eines Verweises, für jede Liste gleich. Das Original zählt nur,
# solange es lebt; sonst ist der Verweis verwaist. Erwartet die Aliase k (Knoten) und v (seine aktuelle Version);
# groesse und sha256 sind die eigene Version oder die des Originals, verweis_anzahl zählt die lebenden Verweise darauf,
# verweis_app nennt die App, die einen Verweis angelegt hat.
ZIEL_JOIN = ("LEFT JOIN knoten z ON z.id = k.ziel_id AND NOT z.geloescht "
             "LEFT JOIN version zv ON zv.id = z.aktuelle_version_id ")
ZIEL_SPALTEN = ("coalesce(v.groesse, zv.groesse) AS groesse, coalesce(v.inhalt_hash, zv.inhalt_hash) AS sha256, "
                "z.name AS ziel_name, z.etag AS ziel_etag, (k.typ = 'verweis' AND z.id IS NULL) AS verwaist, "
                "(SELECT count(*) FROM knoten r WHERE r.ziel_id = k.id AND NOT r.geloescht) AS verweis_anzahl, "
                "CASE WHEN k.typ = 'verweis' THEN (SELECT m.app FROM datei_meta m WHERE m.knoten_id = k.id) END "
                "AS verweis_app")
_VERSION_JOIN = "LEFT JOIN version v ON v.id = k.aktuelle_version_id "
# Verweise, die ein Original mit in den Papierkorb genommen hat (KW-10): gleiche Wurzel, aber nicht in deren Teilbaum
# (der Elternordner ist weder die Wurzel noch mit ihr gelöscht). Alias r; die Wurzel prüft der Aufrufer.
_MITGENOMMEN = ("LEFT JOIN knoten rp ON rp.id = r.parent_id "
                "WHERE r.typ = 'verweis' AND r.geloescht AND r.id <> r.geloescht_wurzel "
                "AND (r.parent_id IS NULL OR (r.parent_id <> r.geloescht_wurzel "
                "AND rp.geloescht_wurzel IS DISTINCT FROM r.geloescht_wurzel))")
# Erste Hälfte des Schlüssels der Papierkorb-Sperre (pg_advisory_xact_lock); die zweite ist das Konto.
_SPERRE_PAPIERKORB = 4_002_620


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
            (besitzer_id, parent_id, nfc(name)),
        )

    async def datei_anlegen(self, besitzer_id, parent_id, name):
        return await self._eine(
            "INSERT INTO knoten (besitzer_id, parent_id, name, typ) "
            "VALUES (%s,%s,%s,'datei') RETURNING *",
            (besitzer_id, parent_id, nfc(name)),
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
            (besitzer_id, parent_id, nfc(name)),
        )

    async def extern_anlegen(self, besitzer_id, parent_id, name, extern_pfad):
        return await self._eine(
            "INSERT INTO knoten (besitzer_id, parent_id, name, typ, extern_pfad) "
            "VALUES (%s,%s,%s,'extern',%s) RETURNING *",
            (besitzer_id, parent_id, nfc(name), extern_pfad),
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
                (besitzer_id, nfc(name)),
            )
        return await self._eine(
            "SELECT * FROM knoten WHERE besitzer_id=%s AND parent_id=%s "
            "AND lower(name)=lower(%s) AND NOT geloescht",
            (besitzer_id, parent_id, nfc(name)),
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
            "WHERE fr.knoten_id = k.id) AS geteilt, "
            "bg.haupt_id, bg.rolle, bg.app AS begleiter_app, "
            "(SELECT count(*) FROM begleiter b JOIN knoten c ON c.id = b.begleiter_id AND NOT c.geloescht "
            "WHERE b.haupt_id = k.id) AS begleiter_anzahl"
        )
        if parent_id is None:
            return await self._alle(
                f"SELECT k.*, {ZIEL_SPALTEN}, {zusatz} FROM knoten k "
                f"{_VERSION_JOIN}{ZIEL_JOIN}"
                "LEFT JOIN begleiter bg ON bg.begleiter_id = k.id "
                "WHERE k.besitzer_id=%s AND k.parent_id IS NULL "
                "AND NOT k.geloescht "
                "ORDER BY CASE k.typ WHEN 'ordner' THEN 0 WHEN 'extern' THEN 1 ELSE 2 END, "
                "lower(k.name)",
                (besitzer_id,),
            )
        return await self._alle(
            f"SELECT k.*, {ZIEL_SPALTEN}, {zusatz} FROM knoten k "
            f"{_VERSION_JOIN}{ZIEL_JOIN}"
            "LEFT JOIN begleiter bg ON bg.begleiter_id = k.id "
            "WHERE k.besitzer_id=%s AND k.parent_id=%s "
            "AND NOT k.geloescht "
            "ORDER BY CASE k.typ WHEN 'ordner' THEN 0 WHEN 'extern' THEN 1 ELSE 2 END, "
            "lower(k.name)",
            (besitzer_id, parent_id),
        )

    async def favoriten(self, besitzer_id):
        return await self._alle(
            f"SELECT k.*, {ZIEL_SPALTEN}, true AS favorit, "
            "(SELECT count(*) FROM knoten c WHERE c.parent_id = k.id AND NOT c.geloescht) "
            "AS kinder_anzahl, "
            "EXISTS(SELECT 1 FROM freigabe fr WHERE fr.knoten_id = k.id) AS geteilt "
            "FROM favorit f JOIN knoten k ON k.id = f.knoten_id "
            f"{_VERSION_JOIN}{ZIEL_JOIN}"
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
            f"SELECT k.*, {ZIEL_SPALTEN}, ob.name AS besitzer_name, "
            "(SELECT count(*) FROM knoten c WHERE c.parent_id=k.id AND NOT c.geloescht) "
            "AS kinder_anzahl "
            "FROM freigabe f "
            "JOIN knoten k ON k.id = f.knoten_id "
            "JOIN benutzer ob ON ob.id = k.besitzer_id "
            f"{_VERSION_JOIN}{ZIEL_JOIN}"
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
            f"SELECT k.*, {ZIEL_SPALTEN}, "
            "(SELECT count(*) FROM knoten c WHERE c.parent_id=k.id AND NOT c.geloescht) "
            "AS kinder_anzahl "
            f"FROM knoten k {_VERSION_JOIN}{ZIEL_JOIN}"
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
            (nfc(neuer_name), knoten_id, besitzer_id),
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

    async def knoten_wiederherstellen(self, besitzer_id, knoten_id, name, parent_id, ausser=()):
        """Holt den Teilbaum einer Papierkorb-Wurzel zurück; die Wurzel selbst unter name in parent_id. Was in ausser
        steht (Begleiter, die eigens neben die Wurzel kommen), bleibt vorerst im Papierkorb."""
        await self.conn.execute(
            "UPDATE knoten SET geloescht=false, geloescht_wurzel=NULL "
            "WHERE geloescht_wurzel=%s AND besitzer_id=%s AND id<>%s AND NOT (id = ANY(%s))",
            (knoten_id, besitzer_id, knoten_id, list(ausser)),
        )
        await self.conn.execute(
            "UPDATE knoten SET geloescht=false, geloescht_wurzel=NULL, name=%s, parent_id=%s, geaendert_am=now() "
            "WHERE id=%s AND besitzer_id=%s",
            (name, parent_id, knoten_id, besitzer_id),
        )

    async def papierkorb(self, besitzer_id):
        """Nur die Wurzeln: was mit einem Ordner gelöscht wurde, steckt in ihm. Auch was vorher einzeln gelöscht wurde
        und in einem gelöschten Ordner liegt, steckt in ihm (HELF-262): jeder Eintrag steht einmal da."""
        # Eine Gruppe ist eine Zeile: die Hauptdatei zählt die mit ihr gelöschten Begleiter; ein allein gelöschter
        # Begleiter nennt Rolle und Hauptdatei (dorthin kommt er beim Wiederherstellen zurück).
        return await self._alle(
            "SELECT k.*, coalesce(v.groesse, zv.groesse) AS groesse, coalesce(v.inhalt_hash, zv.inhalt_hash) AS sha256, "
            "z.name AS ziel_name, z.etag AS ziel_etag, (k.typ = 'verweis' AND z.id IS NULL) AS verwaist, "
            "bg.haupt_id, bg.rolle, hk.name AS haupt_name, "
            "(SELECT count(*) FROM begleiter b JOIN knoten c ON c.id = b.begleiter_id "
            " WHERE b.haupt_id = k.id AND c.geloescht AND c.geloescht_wurzel = k.id) AS begleiter_anzahl, "
            f"(SELECT count(*) FROM knoten r {_MITGENOMMEN} AND r.geloescht_wurzel = k.id) AS verweis_anzahl "
            "FROM knoten k "
            f"{_VERSION_JOIN}{ZIEL_JOIN}"
            "LEFT JOIN begleiter bg ON bg.begleiter_id = k.id "
            "LEFT JOIN knoten hk ON hk.id = bg.haupt_id AND NOT hk.geloescht "
            "WHERE k.besitzer_id=%s AND k.geloescht AND k.geloescht_wurzel = k.id "
            "AND NOT EXISTS (SELECT 1 FROM knoten p WHERE p.id = k.parent_id AND p.geloescht) "
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

    async def papierkorb_sperren(self, besitzer_id):
        """Reiht Arbeiten am Papierkorb eines Kontos hintereinander (endgültig löschen, leeren, wiederherstellen), bis
        zum Ende der Transaktion. Wer die Sperre hat, liest danach den festgeschriebenen Stand: kein Zähler wird doppelt
        gesenkt, und nichts wird entfernt, was gerade zurückgeholt wurde (HELF-262)."""
        await self.conn.execute(
            "SELECT pg_advisory_xact_lock(%s, hashtext(%s))", (_SPERRE_PAPIERKORB, str(besitzer_id))
        )

    async def papierkorb_alle(self, besitzer_id):
        """Alles, was im Papierkorb des Kontos liegt, sichtbar oder nicht (Inhalt gelöschter Ordner, Begleiter,
        mitgenommene Verweise). Grundlage fürs Leeren."""
        zeilen = await self._alle("SELECT id FROM knoten WHERE besitzer_id=%s AND geloescht", (besitzer_id,))
        return [z["id"] for z in zeilen]

    async def endgueltig_betroffen(self, besitzer_id, wurzeln):
        """Alles, was mit diesen Papierkorb-Einträgen endgültig geht: der Inhalt darunter und, was mit einem von ihnen
        in den Papierkorb kam (Begleiter, mitgenommene Verweise), samt deren Inhalt. Jede Kennung einmal."""
        if not wurzeln:
            return []
        zeilen = await self._alle(
            "WITH RECURSIVE menge AS ("
            "  SELECT id FROM knoten WHERE id = ANY(%s) AND besitzer_id=%s AND geloescht "
            "  UNION "
            "  SELECT k.id FROM knoten k JOIN menge m "
            "    ON k.parent_id = m.id OR (k.geloescht AND k.geloescht_wurzel = m.id)"
            ") SELECT id FROM menge",
            (list(wurzeln), besitzer_id),
        )
        return [z["id"] for z in zeilen]

    async def blobrefs_der_knoten(self, ids):
        """Liefert je Blockhash, wie oft ihn die Versionen dieser Knoten nutzen. Grundlage fürs Senken der Zähler."""
        if not ids:
            return []
        return await self._alle(
            "SELECT c.blob_hash AS hash, count(*) AS n "
            "FROM chunk c JOIN version v ON v.id = c.version_id "
            "WHERE v.knoten_id = ANY(%s) GROUP BY c.blob_hash",
            (list(ids),),
        )

    async def blob_refcount_senken(self, besitzer_id, blob_hash, n):
        """Senkt den Zähler; liefert neuen Zähler und Größe des Blocks (oder None, wenn es ihn nicht gibt)."""
        return await self._eine(
            "UPDATE blob SET refcount = refcount - %s "
            "WHERE besitzer_id=%s AND hash=%s RETURNING refcount, groesse",
            (n, besitzer_id, blob_hash),
        )

    async def blob_zeile_loeschen(self, besitzer_id, blob_hash):
        await self.conn.execute(
            "DELETE FROM blob WHERE besitzer_id=%s AND hash=%s AND refcount <= 0",
            (besitzer_id, blob_hash),
        )

    async def knoten_hart_loeschen(self, ids):
        if not ids:
            return
        # ON DELETE CASCADE raeumt Versionen, Chunks und Zuordnungen mit ab.
        await self.conn.execute("DELETE FROM knoten WHERE id = ANY(%s)", (list(ids),))

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
            f"SELECT k.*, {ZIEL_SPALTEN}, bg.haupt_id, bg.rolle FROM knoten k "
            f"{_VERSION_JOIN}{ZIEL_JOIN}LEFT JOIN begleiter bg ON bg.begleiter_id = k.id "
            "WHERE k.parent_id=%s AND NOT k.geloescht "
            "ORDER BY CASE k.typ WHEN 'ordner' THEN 0 WHEN 'extern' THEN 1 ELSE 2 END, lower(k.name), k.id "
            "LIMIT %s OFFSET %s",
            (parent_id, anzahl, ab),
        )

    async def wurzel_seite(self, besitzer_id, ab: int, anzahl: int):
        """Eine Seite der lebenden Knoten auf der obersten Ebene eines Kontos, in derselben Reihenfolge wie
        kinder_seite. Nur für Apps mit "Alles lesen" (KW-3); der Zugriff ist vorher geprüft."""
        return await self._alle(
            f"SELECT k.*, {ZIEL_SPALTEN}, bg.haupt_id, bg.rolle FROM knoten k "
            f"{_VERSION_JOIN}{ZIEL_JOIN}LEFT JOIN begleiter bg ON bg.begleiter_id = k.id "
            "WHERE k.besitzer_id=%s AND k.parent_id IS NULL AND NOT k.geloescht "
            "ORDER BY CASE k.typ WHEN 'ordner' THEN 0 WHEN 'extern' THEN 1 ELSE 2 END, lower(k.name), k.id "
            "LIMIT %s OFFSET %s",
            (besitzer_id, anzahl, ab),
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

    async def journal_entfernt(self, besitzer_id, ids):
        """Ein Eintrag "entfernt" je endgültig gelöschtem Knoten, in der Reihenfolge der Kennungen, mit einer
        Benachrichtigung für alle."""
        if not ids:
            return
        await self.conn.execute(
            "INSERT INTO aenderung (besitzer_id, knoten_id, typ) "
            "SELECT %s, k, 'entfernt' FROM unnest(%s::uuid[]) WITH ORDINALITY AS t(k, n) ORDER BY n",
            (besitzer_id, list(ids)),
        )
        await self.conn.execute("SELECT pg_notify('kellerwolke_journal', %s)", (str(besitzer_id),))

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

    # --- Begleitdateien (Regeln in module/speicher/begleiter.py) --------------

    async def begleiter_der_haupt(self, haupt_id, nur_lebende: bool = True):
        """Begleiter einer Hauptdatei samt Rolle, nach Rolle geordnet."""
        lebend = "AND NOT k.geloescht " if nur_lebende else ""
        return await self._alle(
            "SELECT k.*, b.rolle, b.haupt_id FROM begleiter b JOIN knoten k ON k.id = b.begleiter_id "
            f"WHERE b.haupt_id=%s {lebend}ORDER BY b.rolle",
            (haupt_id,),
        )

    async def begleiter_eintrag(self, begleiter_id):
        """(haupt_id, rolle, app) eines Begleiters oder None."""
        return await self._eine("SELECT haupt_id, rolle, app FROM begleiter WHERE begleiter_id=%s", (begleiter_id,))

    async def begleiter_fuer_rolle(self, haupt_id, rolle):
        """Der eingetragene Begleiter einer Rolle (auch im Papierkorb) oder None."""
        return await self._eine(
            "SELECT k.*, b.rolle, b.haupt_id FROM begleiter b JOIN knoten k ON k.id = b.begleiter_id "
            "WHERE b.haupt_id=%s AND b.rolle=%s",
            (haupt_id, rolle),
        )

    async def begleiter_eintragen(self, haupt_id, begleiter_id, rolle, app):
        await self.conn.execute(
            "INSERT INTO begleiter (begleiter_id, haupt_id, rolle, app) VALUES (%s,%s,%s,%s) "
            "ON CONFLICT (begleiter_id) DO UPDATE SET haupt_id=EXCLUDED.haupt_id, rolle=EXCLUDED.rolle, app=EXCLUDED.app",
            (begleiter_id, haupt_id, rolle, app),
        )

    async def knoten_umziehen(self, besitzer_id, knoten_id, parent_id, name):
        """Ort und Name in einer Anweisung (die Eindeutigkeit gilt für das Ergebnis, nicht für einen Zwischenstand)."""
        await self.conn.execute(
            "UPDATE knoten SET parent_id=%s, name=%s, geaendert_am=now() WHERE id=%s AND besitzer_id=%s",
            (parent_id, nfc(name), knoten_id, besitzer_id),
        )

    async def begleiter_loesen(self, begleiter_id) -> bool:
        cur = await self.conn.execute("DELETE FROM begleiter WHERE begleiter_id=%s", (begleiter_id,))
        return cur.rowcount == 1

    async def als_begleiter_loeschen(self, ids, wurzel):
        """Begleiter wandern mit ihrer Hauptdatei in den Papierkorb: gleiche Wurzel, damit Wiederherstellen und
        endgültiges Löschen sie mitnehmen."""
        if ids:
            await self.conn.execute(
                "UPDATE knoten SET geloescht=true, geloescht_wurzel=%s WHERE id = ANY(%s) AND NOT geloescht",
                (wurzel, list(ids)),
            )

    async def begleiter_im_papierkorb(self, wurzeln):
        """Begleiter, die mit diesen Papierkorb-Wurzeln gelöscht wurden (liegen neben, nicht unter der Wurzel)."""
        if not wurzeln:
            return []
        return await self._alle(
            "SELECT k.* FROM knoten k JOIN begleiter b ON b.begleiter_id = k.id "
            "WHERE k.geloescht AND k.geloescht_wurzel = ANY(%s) AND b.haupt_id = k.geloescht_wurzel",
            (list(wurzeln),),
        )

    # --- Verweise (Regeln in module/speicher/verweise.py) ----------------------------------------------------

    async def knoten_lesend_sperren(self, knoten_id):
        """Der Knoten, gegen gleichzeitiges Löschen gesperrt bis zum Ende der Transaktion (wie ordner_lebt)."""
        return await self._eine("SELECT * FROM knoten WHERE id=%s FOR SHARE", (knoten_id,))

    async def verweis_anlegen(self, besitzer_id, parent_id, name, ziel_id):
        return await self._eine(
            "INSERT INTO knoten (besitzer_id, parent_id, name, typ, ziel_id) "
            "VALUES (%s,%s,%s,'verweis',%s) RETURNING *",
            (besitzer_id, parent_id, nfc(name), ziel_id),
        )

    async def verweise_auf(self, ziel_id):
        """Lebende Verweise auf eine Datei, nach Name."""
        return await self._alle(
            "SELECT k.*, m.app FROM knoten k LEFT JOIN datei_meta m ON m.knoten_id = k.id "
            "WHERE k.ziel_id=%s AND k.typ='verweis' AND NOT k.geloescht ORDER BY lower(k.name), k.id",
            (ziel_id,),
        )

    async def verweise_mitnehmen(self, wurzel_id):
        """Lebende Verweise auf alles, was gerade mit der Wurzel in den Papierkorb kam (Teilbaum und Begleiter), gehen
        mit: gleiche Wurzel, damit Wiederherstellen und endgültiges Löschen sie mitnehmen."""
        return await self._alle(
            "UPDATE knoten SET geloescht=true, geloescht_wurzel=%s "
            "WHERE typ='verweis' AND NOT geloescht "
            "AND ziel_id IN (SELECT id FROM knoten WHERE geloescht AND geloescht_wurzel=%s) RETURNING *",
            (wurzel_id, wurzel_id),
        )

    async def mitgenommene_verweise(self, wurzeln):
        """Verweise, die mit diesen Papierkorb-Wurzeln gelöscht wurden, aber anderswo liegen."""
        if not wurzeln:
            return []
        return await self._alle(
            f"SELECT r.* FROM knoten r {_MITGENOMMEN} AND r.geloescht_wurzel = ANY(%s) ORDER BY lower(r.name), r.id",
            (list(wurzeln),),
        )

    async def verweise_in_folge(self, besitzer_id, knoten_id):
        """Lebende Verweise außerhalb des Teilbaums, die auf eine Datei darin oder einen Begleiter davon zeigen: was
        das Löschen dieses Knotens mitnähme (Folgenvorschau). Mit dem Namen des Originals."""
        return await self._alle(
            "WITH RECURSIVE baum AS ("
            "  SELECT id FROM knoten WHERE id=%s AND besitzer_id=%s AND NOT geloescht "
            "  UNION ALL "
            "  SELECT k.id FROM knoten k JOIN baum b ON k.parent_id = b.id WHERE NOT k.geloescht"
            "), betroffen AS ("
            "  SELECT id FROM baum "
            "  UNION SELECT b.begleiter_id FROM begleiter b JOIN knoten c ON c.id = b.begleiter_id AND NOT c.geloescht "
            "  WHERE b.haupt_id IN (SELECT id FROM baum)"
            ") SELECT r.*, z.name AS ziel_name FROM knoten r JOIN knoten z ON z.id = r.ziel_id "
            "WHERE r.typ='verweis' AND NOT r.geloescht AND r.besitzer_id=%s AND r.ziel_id IN (SELECT id FROM betroffen) "
            "AND r.id NOT IN (SELECT id FROM baum) ORDER BY lower(z.name), lower(r.name), r.id",
            (knoten_id, besitzer_id, besitzer_id),
        )

    async def dateien_mit_inhalt(self, besitzer_id, sha256, grenze: int = 200):
        """Lebende Dateien des Kontos, deren aktuelle Version genau diesen Inhalt hat (sha256), älteste zuerst."""
        return await self._alle(
            "SELECT k.*, v.groesse, v.inhalt_hash AS sha256 FROM version v JOIN knoten k ON k.aktuelle_version_id = v.id "
            "WHERE v.inhalt_hash=%s AND k.besitzer_id=%s AND k.typ='datei' AND NOT k.geloescht "
            "ORDER BY k.erstellt_am, k.id LIMIT %s",
            (sha256, besitzer_id, grenze),
        )

    async def knoten_mit_ziel(self, knoten_id):
        """Ein Knoten mit Größe, Prüfsumme und den Angaben seines Originals (wie eine Zeile der Listen)."""
        return await self._eine(
            f"SELECT k.*, {ZIEL_SPALTEN} FROM knoten k {_VERSION_JOIN}{ZIEL_JOIN}WHERE k.id=%s", (knoten_id,)
        )

"""SpeicherDienst - die Anwendungslogik des Datei-Kerns.

Orchestriert BlobStore (physische Bloecke) und MetadataRepository (logischer
Baum, Versionen, Journal). REST-API und WebDAV rufen ausschliesslich diesen
Dienst, damit ETags und Journal immer konsistent bleiben.
"""

from app.adapters.postgres_metadata import PostgresMetadataRepository


class SpeicherDienst:
    def __init__(self, pool, blobstore) -> None:
        self.pool = pool
        self.blobstore = blobstore

    async def ordner_anlegen(self, besitzer_id, parent_id, name):
        async with self.pool.connection() as conn:
            async with conn.transaction():
                repo = PostgresMetadataRepository(conn)
                knoten = await repo.ordner_anlegen(besitzer_id, parent_id, name)
                await repo.journal_anhaengen(besitzer_id, knoten["id"], "erstellt")
                return knoten

    async def datei_hochladen(self, besitzer_id, parent_id, name, daten):
        # 1. Block zuerst auf die Platte (inhaltsadressiert). neu sagt, ob dieser
        #    Aufruf den Block erzeugt hat - wichtig fuer die Kompensation unten.
        blob_hash, neu = self.blobstore.put(str(besitzer_id), daten)
        groesse = len(daten)
        try:
            async with self.pool.connection() as conn:
                async with conn.transaction():
                    repo = PostgresMetadataRepository(conn)
                    # Atomar anlegen/finden (kein Check-then-act-Race).
                    knoten = await repo.datei_upsert(besitzer_id, parent_id, name)
                    war_neu = knoten["eingefuegt"]
                    # Idempotenz: identischer Inhalt wie aktuelle Version -> No-Op.
                    if not war_neu and knoten["aktuelle_version_id"]:
                        aktuell = await repo.version_holen(knoten["aktuelle_version_id"])
                        if aktuell and aktuell["inhalt_hash"] == blob_hash:
                            return await repo.knoten_holen(knoten["id"])
                    await repo.blob_erhoehen(besitzer_id, blob_hash, groesse)
                    version = await repo.version_anlegen(knoten["id"], groesse, blob_hash, besitzer_id)
                    await repo.chunk_anlegen(version["id"], 0, blob_hash, groesse)
                    # ETag pro Version (eindeutig), nicht der reine Inhalts-Hash:
                    # bei Dedup haetten sonst verschiedene Knoten denselben ETag.
                    await repo.knoten_setzen_version(knoten["id"], version["id"], str(version["id"]))
                    await repo.journal_anhaengen(
                        besitzer_id, knoten["id"], "erstellt" if war_neu else "geaendert", version["id"]
                    )
                    return await repo.knoten_holen(knoten["id"])
        except Exception:
            # Kompensation: nur einen in DIESEM Aufruf neu geschriebenen, jetzt
            # unreferenzierten Block entfernen (die Transaktion wurde zurueckgerollt).
            if neu:
                async with self.pool.connection() as conn:
                    repo = PostgresMetadataRepository(conn)
                    rest = await repo.blob_holen(besitzer_id, blob_hash)
                if not rest:
                    self.blobstore.delete(str(besitzer_id), blob_hash)
            raise

    async def datei_lesen(self, besitzer_id, knoten_id):
        async with self.pool.connection() as conn:
            repo = PostgresMetadataRepository(conn)
            knoten = await repo.knoten_holen(knoten_id)
            if not knoten or knoten["typ"] != "datei" or knoten["geloescht"]:
                raise FileNotFoundError("Datei nicht gefunden")
            teile = await repo.chunks(knoten["aktuelle_version_id"])
        bloecke = [self.blobstore.get(str(besitzer_id), c["blob_hash"]) for c in teile]
        return b"".join(bloecke)

    async def kinder(self, besitzer_id, parent_id):
        async with self.pool.connection() as conn:
            repo = PostgresMetadataRepository(conn)
            return await repo.kinder(besitzer_id, parent_id)

    async def knoten_des_nutzers(self, besitzer_id, knoten_id):
        """Liefert den Knoten nur, wenn er dem Nutzer gehoert - sonst None."""
        async with self.pool.connection() as conn:
            repo = PostgresMetadataRepository(conn)
            knoten = await repo.knoten_holen(knoten_id)
        if not knoten or knoten["besitzer_id"] != besitzer_id:
            return None
        return knoten

    async def knoten_per_pfad(self, besitzer_id, pfad):
        """Loest einen logischen Pfad (z.B. 'Dok/bericht.txt') zum Knoten auf.
        Leerer Pfad liefert None (= Wurzel). Unbekannter Pfad liefert None."""
        teile = [t for t in pfad.split("/") if t]
        parent, knoten = None, None
        async with self.pool.connection() as conn:
            repo = PostgresMetadataRepository(conn)
            for teil in teile:
                knoten = await repo.knoten_finden(besitzer_id, parent, teil)
                if not knoten:
                    return None
                parent = knoten["id"]
        return knoten

    async def groesse(self, knoten) -> int:
        if knoten["typ"] != "datei" or not knoten["aktuelle_version_id"]:
            return 0
        async with self.pool.connection() as conn:
            repo = PostgresMetadataRepository(conn)
            version = await repo.version_holen(knoten["aktuelle_version_id"])
        return version["groesse"] if version else 0

    async def versionen(self, besitzer_id, knoten_id):
        if not await self.knoten_des_nutzers(besitzer_id, knoten_id):
            return None
        async with self.pool.connection() as conn:
            repo = PostgresMetadataRepository(conn)
            return await repo.versionen(knoten_id)

    async def papierkorb(self, besitzer_id):
        async with self.pool.connection() as conn:
            repo = PostgresMetadataRepository(conn)
            return await repo.papierkorb(besitzer_id)

    async def umbenennen(self, besitzer_id, knoten_id, neuer_name):
        async with self.pool.connection() as conn:
            async with conn.transaction():
                repo = PostgresMetadataRepository(conn)
                await repo.knoten_umbenennen(besitzer_id, knoten_id, neuer_name)
                await repo.journal_anhaengen(besitzer_id, knoten_id, "verschoben")
                return await repo.knoten_holen(knoten_id)

    async def verschieben(self, besitzer_id, knoten_id, neuer_parent):
        async with self.pool.connection() as conn:
            async with conn.transaction():
                repo = PostgresMetadataRepository(conn)
                if neuer_parent is not None:
                    ziel = await repo.knoten_holen(neuer_parent)
                    if (not ziel or ziel["besitzer_id"] != besitzer_id
                            or ziel["geloescht"] or ziel["typ"] not in ("ordner", "extern")):
                        raise ValueError("Ungueltiges Ziel")
                    # Verschieben in sich selbst oder einen eigenen Nachkommen verbieten.
                    if await repo.ist_im_teilbaum(knoten_id, neuer_parent):
                        raise ValueError("Zyklus: Ziel liegt im eigenen Teilbaum")
                await repo.knoten_verschieben(besitzer_id, knoten_id, neuer_parent)
                await repo.journal_anhaengen(besitzer_id, knoten_id, "verschoben")
                return await repo.knoten_holen(knoten_id)

    async def umziehen(self, besitzer_id, knoten_id, neuer_parent, neuer_name):
        """Verschieben und/oder Umbenennen atomar in EINER Transaktion (fuer
        WebDAV-MOVE), damit nie ein halb angewandter Zustand entsteht."""
        async with self.pool.connection() as conn:
            async with conn.transaction():
                repo = PostgresMetadataRepository(conn)
                knoten = await repo.knoten_holen(knoten_id)
                if not knoten or knoten["besitzer_id"] != besitzer_id:
                    return None
                if neuer_parent is not None:
                    ziel = await repo.knoten_holen(neuer_parent)
                    if (not ziel or ziel["besitzer_id"] != besitzer_id
                            or ziel["geloescht"] or ziel["typ"] not in ("ordner", "extern")):
                        raise ValueError("Ungueltiges Ziel")
                    if await repo.ist_im_teilbaum(knoten_id, neuer_parent):
                        raise ValueError("Zyklus")
                if neuer_name and neuer_name != knoten["name"]:
                    await repo.knoten_umbenennen(besitzer_id, knoten_id, neuer_name)
                if neuer_parent != knoten["parent_id"]:
                    await repo.knoten_verschieben(besitzer_id, knoten_id, neuer_parent)
                await repo.journal_anhaengen(besitzer_id, knoten_id, "verschoben")
                return await repo.knoten_holen(knoten_id)

    async def loeschen(self, besitzer_id, knoten_id):
        async with self.pool.connection() as conn:
            async with conn.transaction():
                repo = PostgresMetadataRepository(conn)
                await repo.knoten_loeschen(besitzer_id, knoten_id)
                await repo.journal_anhaengen(besitzer_id, knoten_id, "geloescht")

    async def wiederherstellen(self, besitzer_id, knoten_id):
        async with self.pool.connection() as conn:
            async with conn.transaction():
                repo = PostgresMetadataRepository(conn)
                knoten = await repo.knoten_holen(knoten_id)
                if not knoten or knoten["besitzer_id"] != besitzer_id or not knoten["geloescht"]:
                    return None
                name = knoten["name"]
                # Bei Namenskollision mit lebendem Geschwister umbenennen.
                if await repo.knoten_finden(besitzer_id, knoten["parent_id"], name):
                    name = f"{name} (wiederhergestellt)"
                await repo.knoten_wiederherstellen(besitzer_id, knoten_id, name)
                await repo.journal_anhaengen(besitzer_id, knoten_id, "erstellt")
                return await repo.knoten_holen(knoten_id)

    async def journal_seit(self, besitzer_id, seit_seq=0):
        async with self.pool.connection() as conn:
            repo = PostgresMetadataRepository(conn)
            return await repo.journal_seit(besitzer_id, seit_seq)

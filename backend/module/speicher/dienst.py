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
        # 1. Block zuerst auf die Platte (inhaltsadressiert, idempotent).
        blob_hash = self.blobstore.put(str(besitzer_id), daten)
        groesse = len(daten)
        # 2. Metadaten atomar.
        async with self.pool.connection() as conn:
            async with conn.transaction():
                repo = PostgresMetadataRepository(conn)
                await repo.blob_erhoehen(besitzer_id, blob_hash, groesse)
                vorhanden = await repo.knoten_finden(besitzer_id, parent_id, name)
                if vorhanden and vorhanden["typ"] == "datei":
                    knoten = vorhanden
                    typ = "geaendert"
                else:
                    knoten = await repo.datei_anlegen(besitzer_id, parent_id, name)
                    typ = "erstellt"
                version = await repo.version_anlegen(knoten["id"], groesse, blob_hash, besitzer_id)
                await repo.chunk_anlegen(version["id"], 0, blob_hash, groesse)
                await repo.knoten_setzen_version(knoten["id"], version["id"], blob_hash)
                await repo.journal_anhaengen(besitzer_id, knoten["id"], typ, version["id"])
                return await repo.knoten_holen(knoten["id"])

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

    async def versionen(self, knoten_id):
        async with self.pool.connection() as conn:
            repo = PostgresMetadataRepository(conn)
            return await repo.versionen(knoten_id)

    async def umbenennen(self, besitzer_id, knoten_id, neuer_name):
        async with self.pool.connection() as conn:
            async with conn.transaction():
                repo = PostgresMetadataRepository(conn)
                await repo.knoten_umbenennen(knoten_id, neuer_name)
                await repo.journal_anhaengen(besitzer_id, knoten_id, "verschoben")
                return await repo.knoten_holen(knoten_id)

    async def verschieben(self, besitzer_id, knoten_id, neuer_parent):
        async with self.pool.connection() as conn:
            async with conn.transaction():
                repo = PostgresMetadataRepository(conn)
                await repo.knoten_verschieben(knoten_id, neuer_parent)
                await repo.journal_anhaengen(besitzer_id, knoten_id, "verschoben")
                return await repo.knoten_holen(knoten_id)

    async def loeschen(self, besitzer_id, knoten_id):
        async with self.pool.connection() as conn:
            async with conn.transaction():
                repo = PostgresMetadataRepository(conn)
                await repo.knoten_loeschen(knoten_id)
                await repo.journal_anhaengen(besitzer_id, knoten_id, "geloescht")

    async def journal_seit(self, besitzer_id, seit_seq=0):
        async with self.pool.connection() as conn:
            repo = PostgresMetadataRepository(conn)
            return await repo.journal_seit(besitzer_id, seit_seq)

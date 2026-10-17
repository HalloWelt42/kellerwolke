"""Namen in einer Form (NFC): zerlegt geschriebene Namen (macOS) landen zusammengesetzt, werden so gefunden und
ergeben keine zweite, gleich aussehende Datei; die Schemastufe stellt Altbestand um und nummeriert bei Gleichstand."""

import unicodedata

from app import db as dbmod
from app.adapters.postgres_metadata import PostgresMetadataRepository
from module.speicher.dienst import SpeicherDienst
from tests.hilfen import markierter_blobstore

NFD = unicodedata.normalize("NFD", "grün.wav")
NFC = unicodedata.normalize("NFC", "grün.wav")


async def test_zerlegte_namen_werden_zusammengesetzt(pool, tmp_path):
    async with pool.connection() as conn:
        besitzer = (await PostgresMetadataRepository(conn).benutzer_anlegen("familie"))["id"]
    speicher = SpeicherDienst(pool, markierter_blobstore(tmp_path))
    ordner = await speicher.ordner_anlegen(besitzer, None, unicodedata.normalize("NFD", "Übungen"))
    assert ordner["name"] == "Übungen" and NFD != NFC
    eins = await speicher.datei_hochladen(besitzer, ordner["id"], NFD, b"eins")
    zwei = await speicher.datei_hochladen(besitzer, ordner["id"], NFC, b"zwei")
    assert eins["name"] == NFC and eins["id"] == zwei["id"]                     # eine Datei, zwei Versionen
    assert (await speicher.knoten_per_pfad(besitzer, f"Übungen/{NFD}"))["id"] == eins["id"]


async def test_schemastufe_stellt_altbestand_um(pool):
    async with pool.connection() as conn:
        repo = PostgresMetadataRepository(conn)
        besitzer = (await repo.benutzer_anlegen("familie"))["id"]
        ordner = await repo.ordner_anlegen(besitzer, None, "Arbeit")
        await repo.datei_anlegen(besitzer, ordner["id"], NFC)
        # so stand es vorher in der Datenbank: zerlegt, neben dem gleichen Namen zusammengesetzt
        await conn.execute("INSERT INTO knoten (besitzer_id, parent_id, name, typ) VALUES (%s,%s,%s,'datei')",
                           (besitzer, ordner["id"], NFD))
        await dbmod.schema_aus_ordner_anwenden(conn, dbmod.SCHEMA_DIR)
        async with conn.cursor() as cur:
            await cur.execute("SELECT name FROM knoten WHERE parent_id=%s ORDER BY name", (ordner["id"],))
            namen = [z[0] for z in await cur.fetchall()]
    assert namen == ["grün (2).wav", "grün.wav"] and all(unicodedata.is_normalized("NFC", n) for n in namen)

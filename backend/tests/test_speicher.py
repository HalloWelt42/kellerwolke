"""Integrationstests des SpeicherDienst gegen die echte (lokale) PostgreSQL.

Beweist: Upload/Download-Roundtrip, Dedup ueber den Blob-Refcount, neue
Versionen, stabile UUID bei Umbenennen/Verschieben, Soft-Delete und das
Aenderungs-Journal als Sync-Vorbereitung.
"""

import hashlib

import pytest

from app.adapters.filesystem_blobstore import FilesystemBlobStore
from app.adapters.postgres_metadata import PostgresMetadataRepository
from module.speicher.dienst import SpeicherDienst


@pytest.fixture
async def benutzer_id(pool):
    async with pool.connection() as conn:
        repo = PostgresMetadataRepository(conn)
        benutzer = await repo.benutzer_anlegen("familie")
        return benutzer["id"]


@pytest.fixture
def dienst(pool, tmp_path):
    return SpeicherDienst(pool, FilesystemBlobStore(tmp_path))


async def test_upload_und_download(dienst, benutzer_id):
    daten = b"Inhalt mit Umlaut \xc3\xa4\xc3\xb6\xc3\xbc"
    knoten = await dienst.datei_hochladen(benutzer_id, None, "notiz.txt", daten)
    assert knoten["typ"] == "datei"
    assert knoten["etag"] is not None
    zurueck = await dienst.datei_lesen(benutzer_id, knoten["id"])
    assert zurueck == daten


async def test_dedup_ueber_refcount(dienst, benutzer_id, pool):
    daten = b"identischer inhalt"
    inhalt_hash = hashlib.sha256(daten).hexdigest()
    await dienst.datei_hochladen(benutzer_id, None, "a.txt", daten)
    await dienst.datei_hochladen(benutzer_id, None, "b.txt", daten)
    async with pool.connection() as conn:
        repo = PostgresMetadataRepository(conn)
        blob = await repo.blob_holen(benutzer_id, inhalt_hash)
    # Zwei Knoten, aber nur ein physischer Block mit Refcount 2.
    assert blob["refcount"] == 2
    kinder = await dienst.kinder(benutzer_id, None)
    assert len(kinder) == 2


async def test_identischer_reupload_ist_noop(dienst, benutzer_id):
    k1 = await dienst.datei_hochladen(benutzer_id, None, "id.txt", b"gleich")
    k2 = await dienst.datei_hochladen(benutzer_id, None, "id.txt", b"gleich")
    # Gleicher Knoten, gleicher ETag - keine neue Version, kein Journal-Eintrag.
    assert k1["id"] == k2["id"]
    assert k1["etag"] == k2["etag"]
    assert len(await dienst.versionen(k1["id"])) == 1
    assert len(await dienst.journal_seit(benutzer_id, 0)) == 1


async def test_neue_version(dienst, benutzer_id):
    k1 = await dienst.datei_hochladen(benutzer_id, None, "doc.txt", b"version eins")
    k2 = await dienst.datei_hochladen(benutzer_id, None, "doc.txt", b"version zwei")
    # Gleicher Knoten (stabile UUID), neue aktuelle Version.
    assert k1["id"] == k2["id"]
    assert k1["etag"] != k2["etag"]
    versionen = await dienst.versionen(k2["id"])
    assert len(versionen) == 2
    # Neueste Version ist abrufbar.
    assert await dienst.datei_lesen(benutzer_id, k2["id"]) == b"version zwei"


async def test_umbenennen_haelt_uuid(dienst, benutzer_id):
    knoten = await dienst.datei_hochladen(benutzer_id, None, "alt.txt", b"x")
    umbenannt = await dienst.umbenennen(benutzer_id, knoten["id"], "neu.txt")
    assert umbenannt["id"] == knoten["id"]
    assert umbenannt["name"] == "neu.txt"


async def test_verschieben_haelt_uuid(dienst, benutzer_id):
    ordner = await dienst.ordner_anlegen(benutzer_id, None, "Ordner")
    datei = await dienst.datei_hochladen(benutzer_id, None, "frei.txt", b"y")
    verschoben = await dienst.verschieben(benutzer_id, datei["id"], ordner["id"])
    assert verschoben["id"] == datei["id"]
    assert verschoben["parent_id"] == ordner["id"]
    # Im Ordner sichtbar, in der Wurzel nicht mehr.
    assert len(await dienst.kinder(benutzer_id, ordner["id"])) == 1
    wurzel_namen = [k["name"] for k in await dienst.kinder(benutzer_id, None)]
    assert "frei.txt" not in wurzel_namen


async def test_soft_delete_und_papierkorb(dienst, benutzer_id):
    knoten = await dienst.datei_hochladen(benutzer_id, None, "weg.txt", b"z")
    await dienst.loeschen(benutzer_id, knoten["id"])
    namen = [k["name"] for k in await dienst.kinder(benutzer_id, None)]
    assert "weg.txt" not in namen


async def test_journal_zaehlt_monoton(dienst, benutzer_id):
    await dienst.datei_hochladen(benutzer_id, None, "1.txt", b"a")
    await dienst.datei_hochladen(benutzer_id, None, "2.txt", b"b")
    eintraege = await dienst.journal_seit(benutzer_id, 0)
    assert len(eintraege) == 2
    seqs = [e["seq"] for e in eintraege]
    assert seqs == sorted(seqs)
    assert all(e["typ"] == "erstellt" for e in eintraege)

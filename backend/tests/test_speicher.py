"""Integrationstests des SpeicherDienst gegen die echte (lokale) PostgreSQL.

Beweist: Upload/Download-Roundtrip, Dedup ueber den Blob-Refcount, neue
Versionen, stabile UUID bei Umbenennen/Verschieben, Soft-Delete und das
Aenderungs-Journal als Sync-Vorbereitung.
"""

import hashlib
import os
from pathlib import Path

import pytest

from app.adapters.filesystem_blobstore import FilesystemBlobStore
from app.adapters.postgres_metadata import PostgresMetadataRepository
from app.ports import SpeicherNichtVerfuegbar
from module.speicher.dienst import SpeicherDienst
from tests.hilfen import markierter_blobstore


@pytest.fixture
async def benutzer_id(pool):
    async with pool.connection() as conn:
        repo = PostgresMetadataRepository(conn)
        benutzer = await repo.benutzer_anlegen("familie")
        return benutzer["id"]


@pytest.fixture
def dienst(pool, tmp_path):
    return SpeicherDienst(pool, markierter_blobstore(tmp_path))


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
    assert len(await dienst.versionen(benutzer_id, k1["id"])) == 1
    assert len(await dienst.journal_seit(benutzer_id, 0)) == 1


async def test_neue_version(dienst, benutzer_id):
    k1 = await dienst.datei_hochladen(benutzer_id, None, "doc.txt", b"version eins")
    k2 = await dienst.datei_hochladen(benutzer_id, None, "doc.txt", b"version zwei")
    # Gleicher Knoten (stabile UUID), neue aktuelle Version.
    assert k1["id"] == k2["id"]
    assert k1["etag"] != k2["etag"]
    versionen = await dienst.versionen(benutzer_id, k2["id"])
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


async def test_endgueltig_loeschen_einzeln(dienst, benutzer_id):
    knoten = await dienst.datei_hochladen(benutzer_id, None, "endg.txt", b"x")
    # Solange nicht im Papierkorb: kein endgueltiges Loeschen moeglich.
    assert await dienst.knoten_endgueltig_loeschen(benutzer_id, knoten["id"]) is False
    await dienst.loeschen(benutzer_id, knoten["id"])
    assert any(k["name"] == "endg.txt" for k in await dienst.papierkorb(benutzer_id))
    # Endgueltig: aus dem Papierkorb verschwunden.
    assert await dienst.knoten_endgueltig_loeschen(benutzer_id, knoten["id"]) is True
    assert not any(k["name"] == "endg.txt" for k in await dienst.papierkorb(benutzer_id))
    # Erneuter Aufruf trifft keinen Knoten mehr.
    assert await dienst.knoten_endgueltig_loeschen(benutzer_id, knoten["id"]) is False


async def test_als_zip_packt_ordner_rekursiv(dienst, benutzer_id):
    import io
    import zipfile

    ordner = await dienst.ordner_anlegen(benutzer_id, None, "Paket")
    await dienst.datei_hochladen(benutzer_id, ordner["id"], "a.txt", b"AAA")
    unter = await dienst.ordner_anlegen(benutzer_id, ordner["id"], "Unter")
    await dienst.datei_hochladen(benutzer_id, unter["id"], "b.txt", b"BB")
    daten = await dienst.als_zip(benutzer_id, [ordner["id"]])
    assert daten is not None
    with zipfile.ZipFile(io.BytesIO(daten)) as zf:
        namen = set(zf.namelist())
        assert "Paket/a.txt" in namen
        assert "Paket/Unter/b.txt" in namen
        assert zf.read("Paket/a.txt") == b"AAA"
    # Nichts zu packen (leere bzw. nur fremde/ungueltige Auswahl) -> None.
    assert await dienst.als_zip(benutzer_id, []) is None


async def test_externe_quelle_schreibbar(dienst, benutzer_id, tmp_path):
    import uuid

    extern_wurzel = tmp_path / "extern"
    extern_wurzel.mkdir()
    quelle = await dienst.externe_quelle_anlegen(benutzer_id, None, "Stick", str(extern_wurzel))
    assert await dienst.externe_ordner_anlegen(benutzer_id, quelle["id"], "", "Neu") is True
    assert await dienst.externe_datei_schreiben(benutzer_id, quelle["id"], "Neu", "a.txt", b"hallo") is True
    # Auf der Platte und ueber den Lesepfad sichtbar.
    assert (extern_wurzel / "Neu" / "a.txt").read_bytes() == b"hallo"
    assert await dienst.externe_datei_lesen(benutzer_id, quelle["id"], "Neu/a.txt") == b"hallo"
    # Fremder/fehlender Knoten -> False (Isolation).
    assert await dienst.externe_datei_schreiben(benutzer_id, uuid.uuid4(), "", "x.txt", b"y") is False


async def test_als_zip_kollision_und_leerer_ordner(dienst, benutzer_id):
    import io
    import zipfile

    a = await dienst.ordner_anlegen(benutzer_id, None, "A")
    b = await dienst.ordner_anlegen(benutzer_id, None, "B")
    da = await dienst.datei_hochladen(benutzer_id, a["id"], "report.txt", b"AAA")
    db = await dienst.datei_hochladen(benutzer_id, b["id"], "report.txt", b"BBB")
    leer = await dienst.ordner_anlegen(benutzer_id, None, "Leer")
    daten = await dienst.als_zip(benutzer_id, [da["id"], db["id"], leer["id"]])
    with zipfile.ZipFile(io.BytesIO(daten)) as zf:
        namen = zf.namelist()
        # Beide gleichnamigen Dateien erhalten (kein stiller Datenverlust).
        treffer = [n for n in namen if n.startswith("report")]
        assert len(treffer) == 2
        assert {zf.read(n) for n in treffer} == {b"AAA", b"BBB"}
        # Leerer Ordner bleibt als Verzeichniseintrag erhalten.
        assert "Leer/" in namen


async def test_als_zip_zu_gross(dienst, benutzer_id, monkeypatch):
    from types import SimpleNamespace

    from module.speicher import dienst as dmod

    # Nur max_zip kuenstlich klein setzen; die io-Felder vom echten Config
    # uebernehmen, damit die nicht-blockierende Blob-I/O weiter funktioniert.
    monkeypatch.setattr(dmod, "EINSTELLUNGEN", SimpleNamespace(
        max_zip=5,
        io_timeout=dmod.EINSTELLUNGEN.io_timeout,
        io_min_durchsatz=dmod.EINSTELLUNGEN.io_min_durchsatz,
    ))
    knoten = await dienst.datei_hochladen(benutzer_id, None, "gross.txt", b"mehr als fuenf")
    with pytest.raises(dmod.ArchivZuGross):
        await dienst.als_zip(benutzer_id, [knoten["id"]])


async def test_externe_quelle_im_papierkorb_gesperrt(dienst, benutzer_id, tmp_path):
    wurzel = tmp_path / "extern2"
    wurzel.mkdir()
    quelle = await dienst.externe_quelle_anlegen(benutzer_id, None, "Stick", str(wurzel))
    await dienst.loeschen(benutzer_id, quelle["id"])  # in den Papierkorb
    # Im Papierkorb weder lesbar noch beschreibbar.
    assert await dienst.externe_kinder(benutzer_id, quelle["id"]) is None
    assert await dienst.externe_datei_schreiben(benutzer_id, quelle["id"], "", "x.txt", b"y") is False


async def test_journal_zaehlt_monoton(dienst, benutzer_id):
    await dienst.datei_hochladen(benutzer_id, None, "1.txt", b"a")
    await dienst.datei_hochladen(benutzer_id, None, "2.txt", b"b")
    eintraege = await dienst.journal_seit(benutzer_id, 0)
    assert len(eintraege) == 2
    seqs = [e["seq"] for e in eintraege]
    assert seqs == sorted(seqs)
    assert all(e["typ"] == "erstellt" for e in eintraege)


# --- Datenablage verschieben (gehaertet) ------------------------------------

async def test_datenablage_verschieben(pool, benutzer_id, tmp_path):
    quelle = tmp_path / "pool_a"
    ziel = tmp_path / "pool_b"
    dienst = SpeicherDienst(pool, markierter_blobstore(quelle))
    knoten = await dienst.datei_hochladen(benutzer_id, None, "um.txt", b"umzug")
    alt_marker = dienst.blobstore.marker

    await dienst.datenablage_verschieben(str(ziel))

    assert dienst.verschiebung["status"] == "fertig", dienst.verschiebung
    # Aktiver Pfad zeigt aufs Ziel, mit FRISCHEM Marker (eigene Identitaet).
    assert os.path.abspath(await dienst.aktiver_pfad()) == os.path.abspath(str(ziel))
    assert dienst.blobstore.marker and dienst.blobstore.marker != alt_marker
    assert (ziel / ".kellerwolke_pool").read_text().strip() == dienst.blobstore.marker
    # Quelle ist erst nach vollstaendigem Kopieren entfernt.
    assert not quelle.exists()
    # Bestand weiter lesbar, neuer Upload landet im Ziel.
    assert await dienst.datei_lesen(benutzer_id, knoten["id"]) == b"umzug"
    k2 = await dienst.datei_hochladen(benutzer_id, None, "danach.txt", b"frisch")
    assert await dienst.datei_lesen(benutzer_id, k2["id"]) == b"frisch"


async def test_datenablage_verschieben_in_unterordner_scheitert(pool, benutzer_id, tmp_path):
    quelle = tmp_path / "pool_a"
    dienst = SpeicherDienst(pool, markierter_blobstore(quelle))
    await dienst.datei_hochladen(benutzer_id, None, "x.txt", b"x")

    await dienst.datenablage_verschieben(str(quelle / "unter"))

    assert dienst.verschiebung["status"] == "fehler"
    assert "Quellordner" in dienst.verschiebung["fehler"]
    assert quelle.exists()  # nichts angetastet


async def test_datenablage_verschieben_quelle_weg_scheitert(pool, benutzer_id, tmp_path):
    quelle = tmp_path / "pool_a"
    ziel = tmp_path / "pool_b"
    dienst = SpeicherDienst(pool, markierter_blobstore(quelle))
    await dienst.datei_hochladen(benutzer_id, None, "x.txt", b"x")
    # Mount "verschwindet": Marker-Datei weg -> Quelle nicht erreichbar.
    (quelle / ".kellerwolke_pool").unlink()

    await dienst.datenablage_verschieben(str(ziel))

    assert dienst.verschiebung["status"] == "fehler"
    assert not ziel.exists()  # nichts kopiert


# --- Boot-Robustheit: App wartet auf den Mount, statt abzustuerzen -----------

async def test_boot_ohne_mount_kein_absturz(pool, tmp_path):
    pfad = tmp_path / "pool"
    bs = markierter_blobstore(pfad)  # legt Marker an, merkt sich die UUID
    marker = bs.marker
    # DB-Zeile wie aus einem frueheren Lauf (Pfad + Marker bekannt).
    async with pool.connection() as conn:
        async with conn.transaction():
            repo = PostgresMetadataRepository(conn)
            await repo.speicherort_setzen(str(pfad), marker)
    # Mount fehlt beim Boot: Marker-Datei ist weg.
    (pfad / ".kellerwolke_pool").unlink()

    # Frischer Dienst bootet -> kein Absturz, aber Pool nicht erreichbar.
    dienst = SpeicherDienst(pool, FilesystemBlobStore(str(pfad)))
    aktiv = await dienst.speicher_initialisieren(str(pfad))
    assert os.path.abspath(aktiv) == os.path.abspath(str(pfad))
    assert await dienst.speicher_erreichbar() is False
    # Es wurde KEINE falsche Markierung auf der (leeren) Systemplatte angelegt.
    assert not (pfad / ".kellerwolke_pool").exists()

    # Laufwerk kommt zurueck -> heilt sich selbst, ohne Eingriff.
    (pfad / ".kellerwolke_pool").write_text(marker)
    assert await dienst.speicher_erreichbar() is True

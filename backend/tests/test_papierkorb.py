"""Papierkorb mit ganzen Teilbäumen: Löschen markiert alles darunter, Wiederherstellen holt genau diesen Teilbaum
zurück, gelöschte Ordner nehmen nichts mehr an, Dateinamen kollidieren nicht still mit Ordnern."""

import pytest

from app.adapters.postgres_metadata import PostgresMetadataRepository
from app import db as dbmod
from module.speicher.dienst import NameBelegt, SpeicherDienst, ZielUngueltig, name_mit_zusatz
from tests.hilfen import markierter_blobstore


@pytest.fixture
async def benutzer_id(pool):
    async with pool.connection() as conn:
        return (await PostgresMetadataRepository(conn).benutzer_anlegen("familie"))["id"]


@pytest.fixture
def dienst(pool, tmp_path):
    return SpeicherDienst(pool, markierter_blobstore(tmp_path))


async def _baum(dienst, benutzer_id):
    """/P/S/a.txt und /P/b.txt"""
    p = await dienst.ordner_anlegen(benutzer_id, None, "P")
    s = await dienst.ordner_anlegen(benutzer_id, p["id"], "S")
    a = await dienst.datei_hochladen(benutzer_id, s["id"], "a.txt", b"a")
    b = await dienst.datei_hochladen(benutzer_id, p["id"], "b.txt", b"b")
    return p, s, a, b


async def test_loeschen_markiert_teilbaum_und_papierkorb_zeigt_nur_wurzel(dienst, benutzer_id):
    p, s, a, b = await _baum(dienst, benutzer_id)
    await dienst.loeschen(benutzer_id, p["id"])
    for k in (p, s, a, b):
        assert (await dienst.knoten_des_nutzers(benutzer_id, k["id"]))["geloescht"]
    assert [k["id"] for k in await dienst.papierkorb(benutzer_id)] == [p["id"]]
    assert await dienst.favoriten(benutzer_id) == []


async def test_wiederherstellen_holt_den_ganzen_teilbaum(dienst, benutzer_id):
    p, s, a, b = await _baum(dienst, benutzer_id)
    await dienst.loeschen(benutzer_id, p["id"])
    await dienst.wiederherstellen(benutzer_id, p["id"])
    for k in (p, s, a, b):
        assert not (await dienst.knoten_des_nutzers(benutzer_id, k["id"]))["geloescht"]
    assert await dienst.papierkorb(benutzer_id) == []


async def test_vorher_einzeln_geloeschtes_bleibt_im_papierkorb(dienst, benutzer_id):
    p, s, a, b = await _baum(dienst, benutzer_id)
    await dienst.loeschen(benutzer_id, b["id"])
    await dienst.loeschen(benutzer_id, p["id"])
    assert {k["id"] for k in await dienst.papierkorb(benutzer_id)} == {p["id"], b["id"]}
    await dienst.wiederherstellen(benutzer_id, p["id"])
    assert (await dienst.knoten_des_nutzers(benutzer_id, b["id"]))["geloescht"]
    assert [k["id"] for k in await dienst.papierkorb(benutzer_id)] == [b["id"]]


async def test_einzeln_wiederhergestellt_aus_geloeschtem_ordner_landet_in_der_wurzel(dienst, benutzer_id):
    p, s, a, b = await _baum(dienst, benutzer_id)
    await dienst.loeschen(benutzer_id, b["id"])
    await dienst.loeschen(benutzer_id, p["id"])
    zurueck = await dienst.wiederherstellen(benutzer_id, b["id"])
    assert zurueck["parent_id"] is None and not zurueck["geloescht"]
    assert [k["name"] for k in await dienst.kinder(benutzer_id, None)] == ["b.txt"]


async def test_nur_wurzeln_lassen_sich_wiederherstellen(dienst, benutzer_id):
    p, s, a, b = await _baum(dienst, benutzer_id)
    await dienst.loeschen(benutzer_id, p["id"])
    assert await dienst.wiederherstellen(benutzer_id, a["id"]) is None


async def test_wiederherstellen_mit_zusatz_vor_der_endung(dienst, benutzer_id):
    alt = await dienst.datei_hochladen(benutzer_id, None, "Bericht.pdf", b"1")
    await dienst.loeschen(benutzer_id, alt["id"])
    await dienst.datei_hochladen(benutzer_id, None, "Bericht.pdf", b"2")
    zurueck = await dienst.wiederherstellen(benutzer_id, alt["id"])
    assert zurueck["name"] == "Bericht (wiederhergestellt).pdf"


async def test_wiederherstellen_nummeriert_bei_weiterer_kollision(dienst, benutzer_id):
    for _ in range(2):
        k = await dienst.datei_hochladen(benutzer_id, None, "x.txt", b"alt")
        await dienst.loeschen(benutzer_id, k["id"])
        await dienst.datei_hochladen(benutzer_id, None, "x.txt", b"neu")
        await dienst.wiederherstellen(benutzer_id, k["id"])
        neu = await dienst.knoten_per_pfad(benutzer_id, "x.txt")
        await dienst.loeschen(benutzer_id, neu["id"])
    namen = sorted(k["name"] for k in await dienst.kinder(benutzer_id, None))
    assert namen == ["x (wiederhergestellt 2).txt", "x (wiederhergestellt).txt"]


def test_name_mit_zusatz():
    assert name_mit_zusatz("Bericht.pdf", "wiederhergestellt", True) == "Bericht (wiederhergestellt).pdf"
    assert name_mit_zusatz(".bashrc", "z", True) == ".bashrc (z)"
    assert name_mit_zusatz("Projekt.v2", "z", False) == "Projekt.v2 (z)"
    assert name_mit_zusatz("ohne", "z", True) == "ohne (z)"


async def test_in_geloeschten_ordner_geht_nichts_hinein(dienst, benutzer_id):
    p, s, a, b = await _baum(dienst, benutzer_id)
    await dienst.loeschen(benutzer_id, p["id"])
    with pytest.raises(ZielUngueltig):
        await dienst.datei_hochladen(benutzer_id, s["id"], "neu.txt", b"x")
    with pytest.raises(ZielUngueltig):
        await dienst.ordner_anlegen(benutzer_id, s["id"], "Neu")
    lebend = await dienst.ordner_anlegen(benutzer_id, None, "Lebend")
    with pytest.raises(ZielUngueltig):
        await dienst.verschieben(benutzer_id, lebend["id"], s["id"])


async def test_geloeschtes_laesst_sich_nicht_umbenennen_oder_verschieben(dienst, benutzer_id):
    p, s, a, b = await _baum(dienst, benutzer_id)
    await dienst.loeschen(benutzer_id, p["id"])
    with pytest.raises(ZielUngueltig):
        await dienst.umbenennen(benutzer_id, a["id"], "neu.txt")
    with pytest.raises(ZielUngueltig):
        await dienst.verschieben(benutzer_id, a["id"], None)


async def test_datei_mit_ordnernamen_wird_abgewiesen(dienst, benutzer_id):
    await dienst.ordner_anlegen(benutzer_id, None, "Fotos")
    with pytest.raises(NameBelegt):
        await dienst.datei_hochladen(benutzer_id, None, "fotos", b"x")
    ordner = await dienst.knoten_per_pfad(benutzer_id, "Fotos")
    assert ordner["typ"] == "ordner" and ordner["aktuelle_version_id"] is None


async def test_papierkorb_leeren_entfernt_teilbaum_ohne_doppelzaehlung(dienst, benutzer_id, pool):
    p, s, a, b = await _baum(dienst, benutzer_id)
    # Gleicher Inhalt außerhalb: der Block muss die Leerung überleben.
    draussen = await dienst.datei_hochladen(benutzer_id, None, "kopie.txt", b"a")
    await dienst.loeschen(benutzer_id, a["id"])
    await dienst.loeschen(benutzer_id, p["id"])
    await dienst.papierkorb_leeren(benutzer_id)
    assert await dienst.datei_lesen(benutzer_id, draussen["id"]) == b"a"
    assert await dienst.knoten_des_nutzers(benutzer_id, p["id"]) is None


async def test_migration_markiert_bestand(pool, dienst, benutzer_id):
    """Alter Bestand: nur der oberste Knoten war markiert, ohne Wurzel. Die Migration ergänzt beides."""
    p, s, a, b = await _baum(dienst, benutzer_id)
    async with pool.connection() as conn:
        await conn.execute("UPDATE knoten SET geloescht=true, geloescht_wurzel=NULL WHERE id=%s", (p["id"],))
        await dbmod.schema_aus_ordner_anwenden(conn, dbmod.SCHEMA_DIR)
    for k in (s, a, b):
        assert (await dienst.knoten_des_nutzers(benutzer_id, k["id"]))["geloescht_wurzel"] == p["id"]
    assert [k["id"] for k in await dienst.papierkorb(benutzer_id)] == [p["id"]]

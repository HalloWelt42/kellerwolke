"""Tests fuer Volltextsuche und Textextraktion: Suche nach Name und Inhalt,
strenge Nutzer-Isolation (Sicherheit), Ausschluss geloeschter Dateien,
Extraktion aus Text und docx."""

from io import BytesIO

import pytest
from psycopg.rows import dict_row

from module.speicher.dienst import SpeicherDienst
from module.suche.dienst import SuchDienst
from module.suche.extraktion import text_extrahieren
from tests.hilfen import markierter_blobstore


@pytest.fixture
def such(pool):
    return SuchDienst(pool)


@pytest.fixture
def speicher(pool, tmp_path):
    return SpeicherDienst(pool, markierter_blobstore(tmp_path))


async def _user(pool, name):
    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute("INSERT INTO benutzer (name) VALUES (%s) RETURNING id", (name,))
            zeile = await cur.fetchone()
    return zeile["id"]


async def _ablegen(speicher, such, benutzer, name, daten):
    knoten = await speicher.datei_hochladen(benutzer, None, name, daten)
    await such.indexieren(benutzer, knoten["id"], name, daten)
    return knoten


async def test_suche_nach_inhalt(such, speicher, pool):
    benutzer = await _user(pool, "a")
    knoten = await _ablegen(such=such, speicher=speicher, benutzer=benutzer,
                            name="brief.txt", daten="Die Rechnung ist bezahlt".encode())
    treffer = await such.suchen(benutzer, "Rechnung")
    assert any(t["id"] == knoten["id"] for t in treffer)


async def test_suche_nach_dateiname(such, speicher, pool):
    benutzer = await _user(pool, "a")
    knoten = await _ablegen(such=such, speicher=speicher, benutzer=benutzer,
                            name="Urlaubsantrag.txt", daten=b"egal")
    treffer = await such.suchen(benutzer, "Urlaubsantrag")
    assert any(t["id"] == knoten["id"] for t in treffer)


async def test_nutzer_isolation_kein_fremdtreffer(such, speicher, pool):
    a = await _user(pool, "a")
    b = await _user(pool, "b")
    ka = await _ablegen(such=such, speicher=speicher, benutzer=a, name="x.txt", daten=b"geheim")
    kb = await _ablegen(such=such, speicher=speicher, benutzer=b, name="x.txt", daten=b"geheim")
    ids = [t["id"] for t in await such.suchen(a, "geheim")]
    assert ka["id"] in ids
    assert kb["id"] not in ids  # B's Datei darf A NIE erscheinen


async def test_geloeschte_datei_nicht_in_suche(such, speicher, pool):
    benutzer = await _user(pool, "a")
    knoten = await _ablegen(such=such, speicher=speicher, benutzer=benutzer,
                            name="weg.txt", daten=b"findbar")
    await speicher.loeschen(benutzer, knoten["id"])
    assert await such.suchen(benutzer, "findbar") == []


async def test_neuindexierung_aktualisiert(such, speicher, pool):
    benutzer = await _user(pool, "a")
    knoten = await speicher.datei_hochladen(benutzer, None, "v.txt", b"apfel")
    await such.indexieren(benutzer, knoten["id"], "v.txt", b"apfel")
    await such.indexieren(benutzer, knoten["id"], "v.txt", b"birne")
    assert await such.suchen(benutzer, "apfel") == []
    assert any(t["id"] == knoten["id"] for t in await such.suchen(benutzer, "birne"))


async def test_indexieren_fremder_knoten_wird_ignoriert(such, speicher, pool):
    a = await _user(pool, "a")
    b = await _user(pool, "b")
    kb = await speicher.datei_hochladen(b, None, "b.txt", b"geheim")
    # A versucht, B's Knoten unter eigenem Namen zu indexieren - muss wirkungslos sein.
    await such.indexieren(a, kb["id"], "b.txt", b"geheim")
    assert await such.suchen(a, "geheim") == []


def test_grosser_text_wird_begrenzt():
    gross = ("a" * 2_000_000).encode()
    assert len(text_extrahieren("x.txt", gross)) <= 1_000_000


def test_extraktion_text():
    assert "Hallo" in text_extrahieren("a.txt", "Hallo Welt".encode())


def test_extraktion_binaer_leer():
    assert text_extrahieren("bild.png", b"\x89PNG\x00\x01") == ""


def test_extraktion_entfernt_nul_bytes():
    # Eine Textdatei mit eingebettetem NUL (z.B. UTF-16) darf keine 0x00-Bytes
    # liefern - PostgreSQL-Textfelder wuerden sonst die Indexierung sprengen.
    roh = "Rechnung".encode("utf-16-le")  # enthaelt 0x00 zwischen den Zeichen
    text = text_extrahieren("vertrag.txt", roh)
    assert "\x00" not in text


def test_extraktion_docx():
    from docx import Document

    dok = Document()
    dok.add_paragraph("Vertragsabschluss im Mai")
    puffer = BytesIO()
    dok.save(puffer)
    assert "Vertragsabschluss" in text_extrahieren("x.docx", puffer.getvalue())

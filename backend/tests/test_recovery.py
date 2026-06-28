"""Tests fuer das Standalone-Recovery-Tool: baut den Dateibaum aus DB + Objekt-
Pool wieder auf, auch verschachtelt, und meldet fehlende Bloecke."""

import importlib.util
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from app.config import EINSTELLUNGEN
from module.speicher.dienst import SpeicherDienst
from tests.hilfen import markierter_blobstore

_RECOVERY = Path(__file__).resolve().parents[2] / "tools" / "recovery.py"
_spec = importlib.util.spec_from_file_location("recovery", _RECOVERY)
recovery = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(recovery)

TEST_DSN = (f"host={EINSTELLUNGEN.db_host} port={EINSTELLUNGEN.db_port} "
            f"dbname=kellerwolke_test user={EINSTELLUNGEN.db_user} "
            f"password={EINSTELLUNGEN.db_pass}")


async def _user(pool, name):
    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute("INSERT INTO benutzer (name) VALUES (%s) RETURNING id", (name,))
            return (await cur.fetchone())["id"]


async def test_recovery_baut_baum_auf(pool, tmp_path):
    objekte = tmp_path / "objects"
    speicher = SpeicherDienst(pool, markierter_blobstore(objekte))
    benutzer = await _user(pool, "familie")
    ordner = await speicher.ordner_anlegen(benutzer, None, "Dok")
    await speicher.datei_hochladen(benutzer, None, "wurzel.txt", b"Wurzelinhalt")
    await speicher.datei_hochladen(benutzer, ordner["id"], "tief.txt", "Inhalt mit Umlaut ä".encode())

    ausgabe = tmp_path / "wieder"
    with psycopg.connect(TEST_DSN) as conn:
        ergebnis = recovery.rekonstruiere_alle(conn, objekte, ausgabe)

    assert (ausgabe / "familie" / "wurzel.txt").read_bytes() == b"Wurzelinhalt"
    assert (ausgabe / "familie" / "Dok" / "tief.txt").read_bytes() == "Inhalt mit Umlaut ä".encode()
    assert ergebnis["familie"]["dateien"] == 2
    assert ergebnis["familie"]["ordner"] == 1


async def test_recovery_meldet_fehlenden_block(pool, tmp_path):
    objekte = tmp_path / "objects"
    speicher = SpeicherDienst(pool, markierter_blobstore(objekte))
    benutzer = await _user(pool, "x")
    await speicher.datei_hochladen(benutzer, None, "weg.txt", b"verschwindet")
    for p in objekte.rglob("*"):
        if p.is_file():
            p.unlink()

    ausgabe = tmp_path / "wieder"
    with psycopg.connect(TEST_DSN) as conn:
        ergebnis = recovery.rekonstruiere_alle(conn, objekte, ausgabe)
    assert ergebnis["x"]["fehlend"] == 1
    assert ergebnis["x"]["dateien"] == 0

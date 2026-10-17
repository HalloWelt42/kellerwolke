"""Einspielen nach einem Plan: Vorschau ändert nichts, Stände werden Versionen, Begleiter kommen in die Gruppe, nie wird
überschrieben, ein Abbruch setzt fort, Wege aus dem Plan heraus und falsche Prüfsummen werden abgewiesen."""

import hashlib

import pytest

from app.adapters.postgres_metadata import PostgresMetadataRepository
from module.ablage import metadaten
from module.einspielen.dienst import EinspielDienst, PlanFehler
from module.einspielen.plan import Plan
from module.speicher.dienst import SpeicherDienst
from module.suche.dienst import SuchDienst
from tests.hilfen import markierter_blobstore


@pytest.fixture
async def umgebung(pool, tmp_path):
    async with pool.connection() as conn:
        besitzer = (await PostgresMetadataRepository(conn).benutzer_anlegen("familie"))["id"]
    speicher = SpeicherDienst(pool, markierter_blobstore(tmp_path / "pool"))
    ordner = tmp_path / "plan"
    ordner.mkdir()
    return EinspielDienst(pool, speicher, SuchDienst(pool), ordner), speicher, besitzer, ordner


def datei(ordner, name: str, inhalt: bytes) -> dict:
    (ordner / name).write_bytes(inhalt)
    return {"datei": name, "sha256": hashlib.sha256(inhalt).hexdigest()}


def plan(eintraege: list[dict]) -> Plan:
    return Plan.model_validate({"konto": "familie", "titel": "Probe", "eintraege": eintraege})


async def test_vorschau_dann_einspielen(umgebung, pool):
    dienst, speicher, besitzer, ordner = umgebung
    p = plan([
        {**datei(ordner, "t2.json", b'{"stand": 2}'), "ziel": "Apps/Probe/Runde.transkript.json", "app": "Transkription",
         "fruehere": [datei(ordner, "t1.json", b'{"stand": 1}')],
         "begleitet": {"haupt": "Apps/Probe/Runde.wav", "rolle": "transkript", "zusatz": ".transkript.json"}},
        {**datei(ordner, "runde.wav", b"RIFF-runde"), "ziel": "Apps/Probe/Runde.wav", "inhaltstyp": "audio/wav",
         "app": "Transkription", "felder": {"dauer_s": 2.5}},
    ])
    vorher = await dienst.pruefen(p)
    assert [(e.ziel, e.befund) for e in vorher] == [("Apps/Probe/Runde.wav", "neu"), ("Apps/Probe/Runde.transkript.json", "neu")]
    assert await speicher.knoten_per_pfad(besitzer, "Apps") is None               # die Vorschau ändert nichts

    gemeldet = []
    ergebnisse = await dienst.ausfuehren(p, gemeldet.append)
    assert [e.befund for e in ergebnisse] == ["eingespielt", "eingespielt"] and gemeldet == ergebnisse
    ton = await speicher.knoten_per_pfad(besitzer, "Apps/Probe/Runde.wav")
    transkript = await speicher.knoten_per_pfad(besitzer, "Apps/Probe/Runde.transkript.json")
    assert await speicher.datei_lesen(besitzer, transkript["id"]) == b'{"stand": 2}'
    assert len(await speicher.versionen(besitzer, transkript["id"])) == 2
    async with pool.connection() as conn:
        eintrag = await PostgresMetadataRepository(conn).begleiter_eintrag(transkript["id"])
        meta = await metadaten.meta_holen(conn, [ton["id"]])
    assert (eintrag["haupt_id"], eintrag["rolle"]) == (ton["id"], "transkript")
    assert meta[ton["id"]]["inhaltstyp"] == "audio/wav" and meta[ton["id"]]["felder"] == {"dauer_s": 2.5}

    assert {e.befund for e in await dienst.pruefen(p)} == {"vorhanden"}         # ein zweiter Lauf ändert nichts
    assert {e.befund for e in await dienst.ausfuehren(p)} == {"vorhanden"}
    assert len(await speicher.versionen(besitzer, transkript["id"])) == 2


async def test_nie_ueberschreiben_und_fortsetzen(umgebung):
    dienst, speicher, besitzer, ordner = umgebung
    apps = await speicher.ordner_anlegen(besitzer, None, "Apps")
    await speicher.datei_hochladen(besitzer, apps["id"], "fremd.txt", b"anderes")
    await speicher.datei_hochladen(besitzer, apps["id"], "halb.txt", b"stand 1")
    p = plan([
        {**datei(ordner, "f.txt", b"neu"), "ziel": "Apps/fremd.txt"},
        {**datei(ordner, "h2.txt", b"stand 2"), "ziel": "Apps/halb.txt", "fruehere": [datei(ordner, "h1.txt", b"stand 1")]},
    ])
    assert {e.ziel: e.befund for e in await dienst.pruefen(p)} == {"Apps/fremd.txt": "konflikt", "Apps/halb.txt": "fortsetzen"}
    await dienst.ausfuehren(p)
    fremd = await speicher.knoten_per_pfad(besitzer, "Apps/fremd.txt")
    halb = await speicher.knoten_per_pfad(besitzer, "Apps/halb.txt")
    assert await speicher.datei_lesen(besitzer, fremd["id"]) == b"anderes"
    assert await speicher.datei_lesen(besitzer, halb["id"]) == b"stand 2"
    assert len(await speicher.versionen(besitzer, halb["id"])) == 2


async def test_abgewiesen(umgebung):
    dienst, _, _, ordner = umgebung
    d = datei(ordner, "a.txt", b"inhalt")
    falsch = plan([{**d, "sha256": "0" * 64, "ziel": "Apps/a.txt"}])
    assert (await dienst.pruefen(falsch))[0].befund == "fehlt"
    name = plan([{**d, "ziel": "Apps/Runde.txt", "begleitet": {"haupt": "Apps/Runde.wav", "rolle": "notiz", "zusatz": ".notiz.md"}},
                 {**datei(ordner, "r.wav", b"RIFF"), "ziel": "Apps/Runde.wav"}])
    befunde = {e.ziel: e for e in await dienst.pruefen(name)}
    assert befunde["Apps/Runde.txt"].befund == "konflikt" and "Runde.notiz.md" in befunde["Apps/Runde.txt"].grund
    with pytest.raises(PlanFehler):
        await dienst.pruefen(plan([{**d, "datei": "../ausserhalb.txt", "ziel": "Apps/x.txt"}]))
    with pytest.raises(PlanFehler):
        await dienst.pruefen(Plan.model_validate({"konto": "niemand", "eintraege": []}))

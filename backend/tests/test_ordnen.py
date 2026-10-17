"""Ordnen nach Plan: ein Transkript zieht zum Original (die Kopie geht danach in den Papierkorb), die Vorschau ändert
nichts, ein zweiter Lauf meldet erledigt, ein falscher Inhalt oder hängende Begleiter halten den Papierkorb auf."""

import hashlib

import pytest

from app.adapters.postgres_metadata import PostgresMetadataRepository
from module.einspielen.dienst import EinspielDienst
from module.einspielen.ordnen import Ordnung, OrdnenDienst
from module.speicher.dienst import SpeicherDienst
from module.suche.dienst import SuchDienst
from tests.hilfen import markierter_blobstore


@pytest.fixture
async def umgebung(pool, tmp_path):
    async with pool.connection() as conn:
        besitzer = (await PostgresMetadataRepository(conn).benutzer_anlegen("familie"))["id"]
    speicher = SpeicherDienst(pool, markierter_blobstore(tmp_path))
    dienst = OrdnenDienst(EinspielDienst(pool, speicher, SuchDienst(pool), tmp_path))
    arbeit = await speicher.ordner_anlegen(besitzer, None, "Arbeit")
    apps = await speicher.ordner_anlegen(besitzer, None, "Apps")
    original = await speicher.datei_hochladen(besitzer, arbeit["id"], "Runde.wav", b"RIFF-runde")
    kopie = await speicher.datei_hochladen(besitzer, apps["id"], "Runde.wav", b"RIFF-runde")
    transkript = await speicher.datei_hochladen(besitzer, apps["id"], "Runde.transkript.json", b"{}")
    await speicher.begleiter_anhaengen(besitzer, kopie["id"], transkript["id"], "transkript", ".transkript.json")
    return dienst, speicher, besitzer, original, kopie, transkript


def ordnung(sha: str) -> Ordnung:
    return Ordnung.model_validate({"konto": "familie", "schritte": [
        {"art": "begleiter", "datei": "Apps/Runde.transkript.json", "haupt": "Arbeit/Runde.wav", "rolle": "transkript",
         "zusatz": ".transkript.json", "app": "Transkription"},
        {"art": "papierkorb", "ziel": "Apps/Runde.wav", "sha256": sha}]})


async def test_transkript_zum_original(umgebung, pool):
    dienst, speicher, besitzer, original, kopie, transkript = umgebung
    o = ordnung(hashlib.sha256(b"RIFF-runde").hexdigest())
    assert [s.befund for s in await dienst.pruefen(o)] == ["bereit", "bereit"]
    assert (await speicher.knoten_per_pfad(besitzer, "Apps/Runde.wav"))["id"] == kopie["id"]     # Vorschau ändert nichts
    assert [s.befund for s in await dienst.ausfuehren(o)] == ["ausgefuehrt", "ausgefuehrt"]
    neu = await speicher.knoten_per_pfad(besitzer, "Arbeit/Runde.transkript.json")
    assert neu["id"] == transkript["id"]                                                        # Versionen bleiben
    async with pool.connection() as conn:
        eintrag = await PostgresMetadataRepository(conn).begleiter_eintrag(neu["id"])
    assert eintrag["haupt_id"] == original["id"]
    assert await speicher.knoten_per_pfad(besitzer, "Apps/Runde.wav") is None                   # Kopie im Papierkorb
    assert {e["id"] for e in await speicher.papierkorb(besitzer)} >= {kopie["id"]}
    assert [s.befund for s in await dienst.pruefen(o)] == ["erledigt", "erledigt"]


async def test_papierkorb_wird_aufgehalten(umgebung):
    dienst, speicher, besitzer, *_ = umgebung
    falsch = Ordnung.model_validate({"konto": "familie", "schritte": [
        {"art": "papierkorb", "ziel": "Apps/Runde.wav", "sha256": "0" * 64}]})
    assert (await dienst.pruefen(falsch))[0].befund == "konflikt"
    mit_begleiter = Ordnung.model_validate({"konto": "familie", "schritte": [{"art": "papierkorb", "ziel": "Apps/Runde.wav"}]})
    stand = (await dienst.pruefen(mit_begleiter))[0]
    assert stand.befund == "konflikt" and "Runde.transkript.json" in stand.grund
    await dienst.ausfuehren(mit_begleiter)
    assert await speicher.knoten_per_pfad(besitzer, "Apps/Runde.wav") is not None
    samt = Ordnung.model_validate({"konto": "familie", "schritte": [
        {"art": "papierkorb", "ziel": "Apps/Runde.wav", "mit_begleitern": True}]})
    assert [s.befund for s in await dienst.ausfuehren(samt)] == ["ausgefuehrt"]
    assert await speicher.knoten_per_pfad(besitzer, "Apps/Runde.transkript.json") is None      # die Gruppe ging mit

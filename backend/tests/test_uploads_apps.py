"""Fortsetzbare Uploads mit dem App-Schlüssel (KW-11): eine App lädt in Teilen nur dorthin, wo sie schreiben darf,
überschreibt nur mit Stand, und ihr Upload gehört nur ihr."""

import hashlib
import secrets

import httpx
import pytest

from app.main import app_bauen
from app.melder import JournalMelder
from module.ablage.dienst import AblageDienst
from module.anfragen.dienst import AnfragenDienst
from module.appzugang.dienst import AppZugangDienst
from module.auth.dienst import AuthDienst
from module.geraete.dienst import GeraeteDienst
from module.speicher.dienst import SpeicherDienst
from module.suche.dienst import SuchDienst
from module.uploads.dienst import UploadDienst
from module.vorgaenge.dienst import VorgangRegistry
from tests.conftest import TEST_DB, _dsn
from tests.hilfen import markierter_blobstore
from tests.test_ablage import zugang


@pytest.fixture
async def umgebung(pool, tmp_path):
    app = app_bauen()
    app.state.pool = pool
    app.state.auth = AuthDienst(pool)
    app.state.speicher = SpeicherDienst(pool, markierter_blobstore(tmp_path / "pool"))
    app.state.suche = SuchDienst(pool)
    app.state.vorgaenge = VorgangRegistry()
    app.state.appzugang = AppZugangDienst(pool, app.state.speicher)
    app.state.ablage = AblageDienst(pool, app.state.speicher, app.state.appzugang, app.state.suche)
    app.state.anfragen = AnfragenDienst(pool, app.state.speicher)
    app.state.geraete = GeraeteDienst(pool)
    app.state.melder = JournalMelder(_dsn(TEST_DB))
    app.state.uploads = UploadDienst(pool, app.state.speicher, tmp_path / "teile", tage=7)
    await app.state.auth.benutzer_anlegen("chef", "geheim")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/v1/auth/login", json={"kennung": "chef", "passwort": "geheim"})
        yield client, {"X-Kellerwolke-Sitzung": r.json()["token"]}


async def _ordner(client, kopf, pfad) -> dict:
    r = await client.post("/api/v1/ablage/ordner", json={"pfad": pfad}, headers=kopf)
    assert r.status_code == 200, r.text
    return r.json()


async def _teil(client, kopf, uid, versatz, daten):
    return await client.patch(f"/api/v1/uploads/{uid}", content=daten, headers={**kopf, "Upload-Offset": str(versatz)})


async def test_app_laedt_in_teilen_in_ihren_ordner(umgebung):
    client, sitzung = umgebung
    _, tg = await zugang(client, sitzung, "Telegram")
    chat = await _ordner(client, tg, "Apps/Telegram/Familie/2026-11")
    daten = secrets.token_bytes(300_000)
    sha = hashlib.sha256(daten).hexdigest()
    r = await client.post("/api/v1/uploads", json={"name": "Video.mp4", "parent_id": chat["id"], "groesse": len(daten),
                                                   "pruefsumme": sha}, headers=tg)
    assert r.status_code == 201, r.text
    uid = r.json()["id"]
    # gehört nur der App: die Anmeldung sieht ihn nicht, eine andere App auch nicht
    assert (await client.get(f"/api/v1/uploads/{uid}", headers=sitzung)).status_code == 404
    assert (await client.get("/api/v1/uploads", headers=sitzung)).json() == []
    _, andere = await zugang(client, sitzung, "Andere")
    assert (await _teil(client, andere, uid, 0, daten[:10])).status_code == 404
    assert [u["id"] for u in (await client.get("/api/v1/uploads", headers=tg)).json()] == [uid]

    assert (await _teil(client, tg, uid, 0, daten[:100_000])).json()["empfangen"] == 100_000
    r = await _teil(client, tg, uid, 100_000, daten[100_000:])
    assert r.status_code == 200, r.text
    knoten = r.json()["knoten"]
    assert r.json()["fertig"] and knoten["sha256"] == sha and knoten["groesse"] == len(daten)
    ansicht = (await client.get(f"/api/v1/ablage/knoten/{knoten['id']}", headers=tg)).json()
    assert ansicht["app"] == "Telegram" and ansicht["inhaltstyp"] == "video/mp4" and ansicht["sha256"] == sha
    assert (await client.get(f"/api/v1/ablage/pruefsumme/{sha}", headers=tg)).json()[0]["id"] == knoten["id"]


async def test_app_schreibt_nur_im_eigenen_zweig(umgebung):
    client, sitzung = umgebung
    _, iv = await zugang(client, sitzung, "ImageVault")
    _, tg = await zugang(client, sitzung, "Telegram")
    fremd = await _ordner(client, iv, "Apps/ImageVault/2026")
    r = await client.post("/api/v1/uploads", json={"name": "x.jpg", "parent_id": fremd["id"], "groesse": 3}, headers=tg)
    assert r.status_code == 403
    r = await client.post("/api/v1/uploads", json={"name": "x.jpg", "parent_id": None, "groesse": 3}, headers=tg)
    assert r.status_code == 404
    assert (await client.post("/api/v1/uploads", json={"name": "x", "groesse": 3},
                              headers={"Authorization": "Bearer kw_app_falsch"})).status_code == 401


async def test_vorhandene_datei_nur_mit_stand(umgebung):
    client, sitzung = umgebung
    _, tg = await zugang(client, sitzung, "Telegram")
    chat = await _ordner(client, tg, "Apps/Telegram/Chat")
    alt = (await client.put("/api/v1/ablage/datei", params={"pfad": "Apps/Telegram/Chat/Verlauf.md"}, content=b"alt",
                            headers=tg)).json()
    neu = {"name": "Verlauf.md", "parent_id": chat["id"], "groesse": 3}
    assert (await client.post("/api/v1/uploads", json=neu, headers=tg)).status_code == 428
    assert (await client.post("/api/v1/uploads", json={**neu, "nur_neu": True}, headers=tg)).status_code == 412
    assert (await client.post("/api/v1/uploads", json={**neu, "etag": "veraltet"}, headers=tg)).status_code == 412
    r = await client.post("/api/v1/uploads", json={**neu, "etag": alt["etag"]}, headers=tg)
    assert r.status_code == 201, r.text
    uid = r.json()["id"]
    # inzwischen schreibt jemand anderes: der letzte Teil scheitert am Stand, der Upload bleibt liegen
    await client.put("/api/v1/ablage/datei", params={"pfad": "Apps/Telegram/Chat/Verlauf.md"}, content=b"zwischen",
                     headers={**tg, "If-Match": alt["etag"]})
    assert (await _teil(client, tg, uid, 0, b"neu")).status_code == 412
    assert (await client.get(f"/api/v1/uploads/{uid}", headers=tg)).status_code == 200
    assert (await client.delete(f"/api/v1/uploads/{uid}", headers=tg)).status_code == 204


async def test_entzogenes_recht_gilt_beim_letzten_teil(umgebung):
    client, sitzung = umgebung
    z, tg = await zugang(client, sitzung, "Telegram")
    chat = await _ordner(client, tg, "Apps/Telegram/Chat")
    uid = (await client.post("/api/v1/uploads", json={"name": "a.bin", "parent_id": chat["id"], "groesse": 4},
                             headers=tg)).json()["id"]
    assert (await _teil(client, tg, uid, 0, b"ab")).status_code == 200
    nur_lesen = [{"knoten_id": r["knoten_id"], "recht": "lesen"} for r in z["rechte"]]
    assert (await client.put(f"/api/v1/app-zugaenge/{z['id']}/rechte", json={"rechte": nur_lesen},
                             headers=sitzung)).status_code == 200
    assert (await _teil(client, tg, uid, 2, b"cd")).status_code == 403
    assert (await client.get(f"/api/v1/uploads/{uid}", headers=tg)).json()["empfangen"] == 4


async def test_anmeldung_laedt_weiter_wie_bisher_mit_bedingung(umgebung):
    client, sitzung = umgebung
    ordner = (await client.post("/api/v1/dateien/ordner", json={"name": "Fotos"}, headers=sitzung)).json()
    neu = {"name": "a.txt", "parent_id": ordner["id"], "groesse": 2}
    uid = (await client.post("/api/v1/uploads", json=neu, headers=sitzung)).json()["id"]
    erst = (await _teil(client, sitzung, uid, 0, b"v1")).json()["knoten"]
    uid = (await client.post("/api/v1/uploads", json={**neu, "nur_neu": True}, headers=sitzung)).json()["id"]
    assert (await _teil(client, sitzung, uid, 0, b"v2")).status_code == 412
    uid = (await client.post("/api/v1/uploads", json=neu, headers=sitzung)).json()["id"]
    zweit = (await _teil(client, sitzung, uid, 0, b"v2")).json()["knoten"]
    assert zweit["id"] == erst["id"] and zweit["etag"] != erst["etag"]
    versionen = (await client.get(f"/api/v1/dateien/{erst['id']}/versionen", headers=sitzung)).json()
    assert [v["sha256"] for v in versionen] == [hashlib.sha256(b"v2").hexdigest(), hashlib.sha256(b"v1").hexdigest()]

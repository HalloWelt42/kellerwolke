"""Fortsetzbare Uploads: in Teilen senden, nach einer Unterbrechung am empfangenen Stand fortsetzen, mit dem letzten
Teil eintragen (auch als neue Version), Prüfsumme, Grenzen, fremde Konten, Abbruch und Aufräumen."""

import hashlib
import secrets

import httpx
import pytest

from app.main import app_bauen
from module.auth.dienst import AuthDienst
from module.speicher.dienst import SpeicherDienst
from module.suche.dienst import SuchDienst
from module.uploads.dienst import UploadDienst
from module.vorgaenge.dienst import VorgangRegistry
from tests.hilfen import markierter_blobstore


@pytest.fixture
async def umgebung(pool, tmp_path):
    app = app_bauen()
    app.state.pool = pool
    app.state.auth = AuthDienst(pool)
    app.state.speicher = SpeicherDienst(pool, markierter_blobstore(tmp_path / "pool"))
    app.state.suche = SuchDienst(pool)
    app.state.vorgaenge = VorgangRegistry()
    app.state.uploads = UploadDienst(pool, app.state.speicher, tmp_path / "teile", tage=7)
    await app.state.auth.benutzer_anlegen("chef", "geheim")
    await app.state.auth.benutzer_anlegen("gast", "geheim2")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        yield client, app, tmp_path / "teile"


async def _anmelden(client, kennung="chef", passwort="geheim"):
    r = await client.post("/api/v1/auth/login", json={"kennung": kennung, "passwort": passwort})
    return {"X-Kellerwolke-Sitzung": r.json()["token"]}


async def _teil(client, h, uid, versatz, daten):
    return await client.patch(f"/api/v1/uploads/{uid}", content=daten, headers={**h, "Upload-Offset": str(versatz)})


async def test_in_teilen_mit_unterbrechung_und_pruefsumme(umgebung):
    client, app, _ = umgebung
    h = await _anmelden(client)
    ordner = (await client.post("/api/v1/dateien/ordner", json={"name": "Fotos"}, headers=h)).json()
    daten = secrets.token_bytes(250_000)
    r = await client.post("/api/v1/uploads", json={"name": "IMG_2041.heic", "parent_id": ordner["id"],
                                                   "groesse": len(daten),
                                                   "pruefsumme": hashlib.sha256(daten).hexdigest()}, headers=h)
    assert r.status_code == 201 and r.json()["empfangen"] == 0
    uid = r.json()["id"]
    assert (await _teil(client, h, uid, 0, daten[:100_000])).json()["empfangen"] == 100_000
    # Unterbrechung: der Sender weiß nicht, ob das zweite Teil ankam - er fragt nach und setzt fort.
    falsch = await _teil(client, h, uid, 50_000, daten[50_000:150_000])
    assert falsch.status_code == 409 and falsch.headers["upload-offset"] == "100000"
    weiter = (await client.get(f"/api/v1/uploads/{uid}", headers=h)).json()["empfangen"]
    r = await _teil(client, h, uid, weiter, daten[weiter:200_000])
    assert r.json()["empfangen"] == 200_000 and not r.json()["fertig"]
    r = await _teil(client, h, uid, 200_000, daten[200_000:])
    assert r.status_code == 200 and r.json()["fertig"] and r.json()["knoten"]["name"] == "IMG_2041.heic"
    knoten = r.json()["knoten"]
    assert (await client.get(f"/api/v1/dateien/{knoten['id']}/inhalt", headers=h)).content == daten
    assert (await client.get(f"/api/v1/uploads/{uid}", headers=h)).status_code == 404
    assert (await client.get("/api/v1/uploads", headers=h)).json() == []


async def test_falsche_pruefsumme_traegt_nichts_ein(umgebung):
    client, app, _ = umgebung
    h = await _anmelden(client)
    r = await client.post("/api/v1/uploads", json={"name": "x.bin", "groesse": 5, "pruefsumme": "0" * 64}, headers=h)
    r = await _teil(client, h, r.json()["id"], 0, b"hallo")
    assert r.status_code == 422
    assert [k["name"] for k in (await client.get("/api/v1/dateien", headers=h)).json()] == []


async def test_gleicher_name_wird_neue_version(umgebung):
    client, app, _ = umgebung
    h = await _anmelden(client)
    for inhalt in (b"erste", b"zweite Fassung"):
        r = await client.post("/api/v1/uploads", json={"name": "notiz.txt", "groesse": len(inhalt)}, headers=h)
        r = await _teil(client, h, r.json()["id"], 0, inhalt)
        assert r.json()["fertig"]
    k = r.json()["knoten"]
    assert len((await client.get(f"/api/v1/dateien/{k['id']}/versionen", headers=h)).json()) == 2


async def test_grenzen_und_fehler(umgebung):
    client, app, _ = umgebung
    h = await _anmelden(client)
    assert (await client.post("/api/v1/uploads", json={"name": "a/b", "groesse": 1}, headers=h)).status_code == 422
    r = await client.post("/api/v1/uploads", json={"name": "a.txt", "groesse": 10}, headers=h)
    uid = r.json()["id"]
    assert (await client.patch(f"/api/v1/uploads/{uid}", content=b"x", headers=h)).status_code == 428
    zuviel = await _teil(client, h, uid, 0, b"x" * 11)
    assert zuviel.status_code == 413
    assert (await client.get(f"/api/v1/uploads/{uid}", headers=h)).json()["empfangen"] == 0  # verworfen
    hg = await _anmelden(client, "gast", "geheim2")
    assert (await client.get(f"/api/v1/uploads/{uid}", headers=hg)).status_code == 404       # fremdes Konto
    assert (await _teil(client, hg, uid, 0, b"x")).status_code == 404
    assert (await client.delete(f"/api/v1/uploads/{uid}", headers=hg)).status_code == 404


async def test_ziel_weg_vor_dem_letzten_teil(umgebung):
    client, app, _ = umgebung
    h = await _anmelden(client)
    ordner = (await client.post("/api/v1/dateien/ordner", json={"name": "Weg"}, headers=h)).json()
    r = await client.post("/api/v1/uploads", json={"name": "a.txt", "parent_id": ordner["id"], "groesse": 2}, headers=h)
    uid = r.json()["id"]
    await _teil(client, h, uid, 0, b"a")
    await client.delete(f"/api/v1/dateien/{ordner['id']}", headers=h)
    assert (await _teil(client, h, uid, 1, b"b")).status_code == 404
    assert (await client.get(f"/api/v1/uploads/{uid}", headers=h)).json()["empfangen"] == 2   # bleibt bis Abbruch
    assert (await client.delete(f"/api/v1/uploads/{uid}", headers=h)).status_code == 204
    assert (await client.get(f"/api/v1/uploads/{uid}", headers=h)).status_code == 404


async def test_aufraeumen_entfernt_ruhende_und_verwaiste(umgebung):
    client, app, teile = umgebung
    h = await _anmelden(client)
    alt = (await client.post("/api/v1/uploads", json={"name": "alt.txt", "groesse": 5}, headers=h)).json()["id"]
    frisch = (await client.post("/api/v1/uploads", json={"name": "frisch.txt", "groesse": 5}, headers=h)).json()["id"]
    await _teil(client, h, alt, 0, b"ab")
    async with app.state.pool.connection() as conn:
        await conn.execute("UPDATE upload SET zuletzt_am = now() - interval '8 days' WHERE id=%s", (alt,))
    benutzer = next(b for b in await app.state.auth.liste_benutzer() if b["name"] == "chef")
    verwaist = teile / str(benutzer["id"]) / "00000000-0000-0000-0000-000000000000"
    verwaist.write_bytes(b"rest")
    import os
    os.utime(verwaist, (0, 0))
    assert await app.state.uploads.aufraeumen() == 2
    assert [u["id"] for u in (await client.get("/api/v1/uploads", headers=h)).json()] == [frisch]
    assert not verwaist.exists()

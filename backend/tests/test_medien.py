"""Medien im Kern: Zugang per Cookie statt Schlüssel in der Adresse, Vorschau in zwei Stufen aus einem Dekodiervorgang,
versionsgebundenes Zwischenspeichern, geteilte Dateien, abgeschottete Auslieferung, Aufräumen der Ablage."""

import io

import httpx
import pytest
from PIL import Image

from app.main import app_bauen
from module.auth.dienst import AuthDienst
from module.medien.vorschau import VorschauDienst
from module.speicher.dienst import SpeicherDienst
from module.suche.dienst import SuchDienst
from module.vorgaenge.dienst import VorgangRegistry
from tests.hilfen import markierter_blobstore


def _jpeg(farbe=(200, 30, 30), groesse=(1200, 800)) -> bytes:
    aus = io.BytesIO()
    Image.new("RGB", groesse, farbe).save(aus, format="JPEG")
    return aus.getvalue()


@pytest.fixture
async def umgebung(pool, tmp_path):
    app = app_bauen()
    app.state.pool = pool
    app.state.auth = AuthDienst(pool)
    app.state.speicher = SpeicherDienst(pool, markierter_blobstore(tmp_path / "pool"))
    app.state.suche = SuchDienst(pool)
    app.state.vorgaenge = VorgangRegistry()
    app.state.medien = VorschauDienst(pool, app.state.speicher, tmp_path / "vorschau")
    await app.state.auth.benutzer_anlegen("chef", "geheim", rolle="admin")
    await app.state.auth.benutzer_anlegen("gast", "geheim2")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        yield client, app, tmp_path / "vorschau"


async def _anmelden(client, kennung="chef", passwort="geheim"):
    r = await client.post("/api/v1/auth/login", json={"kennung": kennung, "passwort": passwort})
    return {"X-Kellerwolke-Sitzung": r.json()["token"]}


async def _hoch(client, h, name, daten):
    r = await client.post("/api/v1/dateien/upload", files={"datei": (name, daten, "application/octet-stream")},
                          headers=h)
    assert r.status_code == 200, r.text
    return r.json()


async def test_zugang_per_cookie_und_nur_dafuer(umgebung):
    client, app, _ = umgebung
    h = await _anmelden(client)
    k = await _hoch(client, h, "rot.jpg", _jpeg())
    url = f"/api/v1/medien/vorschau/{k['id']}?v={k['etag']}"
    assert (await client.get(url)).status_code == 401
    assert (await client.get(url + "&t=" + h["X-Kellerwolke-Sitzung"])).status_code == 401  # kein Schlüssel in Adressen
    r = await client.post("/api/v1/medien/zugang", headers=h)
    assert r.status_code == 204
    keks = r.headers["set-cookie"].lower()
    assert "httponly" in keks and "samesite=strict" in keks and "path=/api/v1/medien" in keks
    assert (await client.get(url)).status_code == 200
    # Der Cookie gilt nur für Medien.
    client.cookies.set("kw_medien", h["X-Kellerwolke-Sitzung"])
    assert (await client.get("/api/v1/dateien")).status_code == 401
    # Abmelden beendet auch den Medien-Zugang.
    await client.post("/api/v1/auth/logout", headers=h)
    assert (await client.get(url)).status_code == 401


async def test_vorschau_zwei_stufen_einmal_dekodiert_und_versionsgebunden(umgebung):
    client, app, ablage = umgebung
    h = await _anmelden(client)
    k = await _hoch(client, h, "rot.jpg", _jpeg())
    r = await client.get(f"/api/v1/medien/vorschau/{k['id']}?stufe=klein&v={k['etag']}", headers=h)
    assert r.status_code == 200 and r.headers["content-type"] == "image/webp"
    assert "immutable" in r.headers["cache-control"]
    with Image.open(io.BytesIO(r.content)) as im:
        assert max(im.size) == 160
    assert sorted(p.name for p in ablage.rglob("*.webp")) == [f"{k['etag']}_gross.webp", f"{k['etag']}_klein.webp"]
    ohne = await client.get(f"/api/v1/medien/vorschau/{k['id']}", headers=h)
    assert ohne.headers["cache-control"] == "private, no-cache"
    with Image.open(io.BytesIO(ohne.content)) as im:
        assert max(im.size) == 480
    neu = await _hoch(client, h, "rot.jpg", _jpeg((0, 0, 255)))
    assert neu["etag"] != k["etag"]
    alt = await client.get(f"/api/v1/medien/vorschau/{k['id']}?v={k['etag']}", headers=h)
    assert alt.headers["cache-control"] == "private, no-cache"  # veralteter Stand wird nicht festgeschrieben


async def test_geteilte_medien_und_geloeschte(umgebung):
    client, app, _ = umgebung
    h = await _anmelden(client)
    hg = await _anmelden(client, "gast", "geheim2")
    k = await _hoch(client, h, "strand.jpg", _jpeg())
    gast = next(b for b in await app.state.auth.liste_benutzer() if b["name"] == "gast")
    assert (await client.get(f"/api/v1/medien/voll/{k['id']}", headers=hg)).status_code == 404
    await client.post(f"/api/v1/dateien/{k['id']}/teilen", json={"ziel_benutzer_id": str(gast["id"])}, headers=h)
    assert (await client.get(f"/api/v1/medien/vorschau/{k['id']}", headers=hg)).status_code == 200
    voll = await client.get(f"/api/v1/medien/voll/{k['id']}", headers=hg)
    assert voll.status_code == 200 and voll.content.startswith(b"\xff\xd8")
    assert voll.headers["content-disposition"].startswith("inline")
    await client.delete(f"/api/v1/dateien/{k['id']}", headers=h)
    assert (await client.get(f"/api/v1/medien/voll/{k['id']}", headers=h)).status_code == 404


async def test_svg_abgeschottet_und_kaputtes_bild_415(umgebung):
    client, app, _ = umgebung
    h = await _anmelden(client)
    svg = await _hoch(client, h, "boese.svg", b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>')
    r = await client.get(f"/api/v1/medien/voll/{svg['id']}", headers=h)
    assert r.status_code == 200 and "sandbox" in r.headers["content-security-policy"]
    assert r.headers["x-content-type-options"] == "nosniff"
    kaputt = await _hoch(client, h, "kaputt.jpg", b"kein bild")
    assert (await client.get(f"/api/v1/medien/vorschau/{kaputt['id']}", headers=h)).status_code == 415


async def test_strom_mit_bereichen(umgebung):
    client, app, _ = umgebung
    h = await _anmelden(client)
    daten = bytes(range(256)) * 40
    k = await _hoch(client, h, "lied.mp3", daten)
    ganz = await client.get(f"/api/v1/medien/strom/{k['id']}", headers=h)
    assert ganz.status_code == 200 and ganz.content == daten and ganz.headers["content-type"] == "audio/mpeg"
    teil = await client.get(f"/api/v1/medien/strom/{k['id']}", headers={**h, "Range": "bytes=-100"})
    assert teil.status_code == 206 and teil.content == daten[-100:]
    assert (await client.get(f"/api/v1/medien/strom/{k['id']}", headers={**h, "Range": "bytes=999999-"})).status_code == 416


async def test_liste_und_medienart(umgebung):
    client, app, _ = umgebung
    h = await _anmelden(client)
    ordner = (await client.post("/api/v1/dateien/ordner", json={"name": "Urlaub"}, headers=h)).json()
    r = await client.post("/api/v1/dateien/upload", data={"parent_id": ordner["id"]},
                          files={"datei": ("film.mp4", b"v", "video/mp4")}, headers=h)
    await _hoch(client, h, "text.txt", b"t")
    alle = (await client.get("/api/v1/medien/alle", headers=h)).json()
    assert [(m["name"], m["art"], [p["name"] for p in m["pfad"]]) for m in alle] == [("film.mp4", "video", ["Urlaub"])]
    assert alle[0]["etag"] == r.json()["etag"]
    kinder = (await client.get("/api/v1/dateien", headers=h)).json()
    assert {k["name"]: k["medienart"] for k in kinder} == {"Urlaub": None, "text.txt": None}


async def test_aufraeumen_behaelt_nur_aktuelle_staende(umgebung):
    client, app, ablage = umgebung
    h = await _anmelden(client)
    bleibt = await _hoch(client, h, "bleibt.jpg", _jpeg())
    alt = await _hoch(client, h, "neu.jpg", _jpeg())
    weg = await _hoch(client, h, "weg.jpg", _jpeg())
    for k in (bleibt, alt, weg):
        await client.get(f"/api/v1/medien/vorschau/{k['id']}", headers=h)
    await _hoch(client, h, "neu.jpg", _jpeg((0, 255, 0)))
    await client.delete(f"/api/v1/dateien/{weg['id']}", headers=h)
    (ablage / "zz").mkdir()
    (ablage / "zz" / "liegen.tmp").write_bytes(b"x")
    entfernt = await app.state.medien.aufraeumen()
    assert entfernt == 4  # je zwei Stufen der überholten und der gelöschten Version
    assert {p.name.split("_")[0] for p in ablage.rglob("*.webp")} == {bleibt["etag"]}
    assert (ablage / "zz" / "liegen.tmp").exists()  # frische Zwischendateien bleiben

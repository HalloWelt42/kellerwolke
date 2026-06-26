"""Tests fuer den WebDAV-Adapter: OPTIONS, Auth, PUT/GET, PROPFIND, MKCOL,
MOVE, DELETE - gegen die ASGI-App mit Basic-Auth."""

import httpx
import pytest

from app.adapters.filesystem_blobstore import FilesystemBlobStore
from app.main import app_bauen
from module.auth.dienst import AuthDienst
from module.speicher.dienst import SpeicherDienst
from module.suche.dienst import SuchDienst

AUTH = ("chef", "geheim")


@pytest.fixture
async def client(pool, tmp_path):
    app = app_bauen()
    app.state.pool = pool
    app.state.auth = AuthDienst(pool)
    app.state.speicher = SpeicherDienst(pool, FilesystemBlobStore(tmp_path))
    app.state.suche = SuchDienst(pool)
    await app.state.auth.benutzer_anlegen("chef", "geheim", rolle="admin")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_options_meldet_dav(client):
    r = await client.request("OPTIONS", "/webdav")
    assert r.status_code == 200
    assert "1" in r.headers.get("dav", "")


async def test_propfind_ohne_auth_401(client):
    r = await client.request("PROPFIND", "/webdav/", headers={"Depth": "0"})
    assert r.status_code == 401


async def test_put_get_und_propfind(client):
    r = await client.request("PUT", "/webdav/notiz.txt", content=b"Hallo DAV", auth=AUTH)
    assert r.status_code == 201
    r = await client.get("/webdav/notiz.txt", auth=AUTH)
    assert r.content == b"Hallo DAV"
    r = await client.request("PROPFIND", "/webdav/", headers={"Depth": "1"}, auth=AUTH)
    assert r.status_code == 207
    assert "notiz.txt" in r.text


async def test_mkcol_und_datei_darin(client):
    assert (await client.request("MKCOL", "/webdav/Dok", auth=AUTH)).status_code == 201
    assert (await client.request("PUT", "/webdav/Dok/a.txt", content=b"x", auth=AUTH)).status_code == 201
    assert (await client.get("/webdav/Dok/a.txt", auth=AUTH)).content == b"x"


async def test_move_benennt_um(client):
    await client.request("PUT", "/webdav/alt.txt", content=b"x", auth=AUTH)
    r = await client.request(
        "MOVE", "/webdav/alt.txt", headers={"Destination": "/webdav/neu.txt"}, auth=AUTH
    )
    assert r.status_code == 201
    assert (await client.get("/webdav/neu.txt", auth=AUTH)).status_code == 200
    assert (await client.get("/webdav/alt.txt", auth=AUTH)).status_code == 404


async def test_delete(client):
    await client.request("PUT", "/webdav/weg.txt", content=b"x", auth=AUTH)
    assert (await client.request("DELETE", "/webdav/weg.txt", auth=AUTH)).status_code == 204
    assert (await client.get("/webdav/weg.txt", auth=AUTH)).status_code == 404


async def test_falsche_anmeldung_401(client):
    r = await client.request("PROPFIND", "/webdav/", auth=("chef", "falsch"))
    assert r.status_code == 401


async def test_put_ueberschreiben_liefert_204(client):
    r1 = await client.request("PUT", "/webdav/u.txt", content=b"eins", auth=AUTH)
    assert r1.status_code == 201
    r2 = await client.request("PUT", "/webdav/u.txt", content=b"zwei", auth=AUTH)
    assert r2.status_code == 204
    assert (await client.get("/webdav/u.txt", auth=AUTH)).content == b"zwei"


async def test_getlastmodified_ist_gmt(client):
    await client.request("PUT", "/webdav/d.txt", content=b"x", auth=AUTH)
    r = await client.request("PROPFIND", "/webdav/", headers={"Depth": "1"}, auth=AUTH)
    assert "GMT" in r.text
    assert "+0000" not in r.text


async def test_move_in_ordner_mit_neuem_namen(client):
    await client.request("MKCOL", "/webdav/Ziel", auth=AUTH)
    await client.request("PUT", "/webdav/quelle.txt", content=b"inhalt", auth=AUTH)
    r = await client.request(
        "MOVE", "/webdav/quelle.txt",
        headers={"Destination": "/webdav/Ziel/umbenannt.txt"}, auth=AUTH,
    )
    assert r.status_code == 201
    assert (await client.get("/webdav/Ziel/umbenannt.txt", auth=AUTH)).content == b"inhalt"
    assert (await client.get("/webdav/quelle.txt", auth=AUTH)).status_code == 404

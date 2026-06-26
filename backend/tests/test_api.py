"""API-Tests (httpx gegen die ASGI-App): Login, Datei-Lebenszyklus, Suche,
Fremdzugriff-Schutz (Isolation) und Admin-Guard."""

import httpx
import pytest

from app.adapters.filesystem_blobstore import FilesystemBlobStore
from app.main import app_bauen
from module.auth.dienst import AuthDienst
from module.speicher.dienst import SpeicherDienst
from module.suche.dienst import SuchDienst


@pytest.fixture
async def umgebung(pool, tmp_path):
    app = app_bauen()
    app.state.pool = pool
    app.state.auth = AuthDienst(pool)
    app.state.speicher = SpeicherDienst(pool, FilesystemBlobStore(tmp_path))
    app.state.suche = SuchDienst(pool)
    await app.state.auth.benutzer_anlegen("chef", "geheim", rolle="admin")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, app


async def _anmelden(client, kennung="chef", passwort="geheim"):
    antwort = await client.post(
        "/api/v1/auth/login", json={"kennung": kennung, "passwort": passwort}
    )
    assert antwort.status_code == 200, antwort.text
    return {"X-Kellerwolke-Sitzung": antwort.json()["token"]}


async def _upload(client, headers, name, daten):
    return await client.post(
        "/api/v1/dateien/upload",
        files={"datei": (name, daten, "application/octet-stream")},
        headers=headers,
    )


async def test_health(umgebung):
    client, _ = umgebung
    r = await client.get("/api/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


async def test_login_und_status(umgebung):
    client, _ = umgebung
    h = await _anmelden(client)
    r = await client.get("/api/v1/auth/status", headers=h)
    assert r.json()["angemeldet"] is True
    assert r.json()["benutzer"]["name"] == "chef"


async def test_login_falsch(umgebung):
    client, _ = umgebung
    r = await client.post("/api/v1/auth/login", json={"kennung": "chef", "passwort": "falsch"})
    assert r.status_code == 401


async def test_ohne_anmeldung_401(umgebung):
    client, _ = umgebung
    assert (await client.get("/api/v1/dateien")).status_code == 401


async def test_upload_liste_download(umgebung):
    client, _ = umgebung
    h = await _anmelden(client)
    r = await _upload(client, h, "notiz.txt", b"Hallo Welt")
    assert r.status_code == 200, r.text
    knoten_id = r.json()["id"]
    liste = (await client.get("/api/v1/dateien", headers=h)).json()
    assert any(k["name"] == "notiz.txt" for k in liste)
    inhalt = await client.get(f"/api/v1/dateien/{knoten_id}/inhalt", headers=h)
    assert inhalt.content == b"Hallo Welt"


async def test_ordner_und_verschieben(umgebung):
    client, _ = umgebung
    h = await _anmelden(client)
    ordner = (await client.post("/api/v1/dateien/ordner", json={"name": "Dok"}, headers=h)).json()
    datei = (await _upload(client, h, "a.txt", b"x")).json()
    r = await client.patch(
        f"/api/v1/dateien/{datei['id']}/ort", json={"parent_id": ordner["id"]}, headers=h
    )
    assert r.status_code == 200
    kinder = (await client.get(f"/api/v1/dateien?parent_id={ordner['id']}", headers=h)).json()
    assert any(k["id"] == datei["id"] for k in kinder)


async def test_loeschen_papierkorb_wiederherstellen(umgebung):
    client, _ = umgebung
    h = await _anmelden(client)
    datei = (await _upload(client, h, "weg.txt", b"x")).json()
    assert (await client.delete(f"/api/v1/dateien/{datei['id']}", headers=h)).status_code == 204
    assert all(k["id"] != datei["id"] for k in (await client.get("/api/v1/dateien", headers=h)).json())
    papier = (await client.get("/api/v1/dateien/papierkorb", headers=h)).json()
    assert any(k["id"] == datei["id"] for k in papier)
    r = await client.post(f"/api/v1/dateien/{datei['id']}/wiederherstellen", headers=h)
    assert r.status_code == 200
    assert any(k["id"] == datei["id"] for k in (await client.get("/api/v1/dateien", headers=h)).json())


async def test_suche_route(umgebung):
    client, _ = umgebung
    h = await _anmelden(client)
    await _upload(client, h, "brief.txt", "Rechnung bezahlt".encode())
    r = await client.get("/api/v1/suche", params={"q": "Rechnung"}, headers=h)
    assert r.status_code == 200
    assert any(k["name"] == "brief.txt" for k in r.json())


async def test_fremdzugriff_gibt_404(umgebung):
    client, app = umgebung
    h_chef = await _anmelden(client)
    datei = (await _upload(client, h_chef, "privat.txt", b"geheim")).json()
    await app.state.auth.benutzer_anlegen("gast", "pw")
    h_gast = await _anmelden(client, "gast", "pw")
    r = await client.get(f"/api/v1/dateien/{datei['id']}/inhalt", headers=h_gast)
    assert r.status_code == 404  # Existenz darf nicht preisgegeben werden


async def test_admin_guard(umgebung):
    client, app = umgebung
    await app.state.auth.benutzer_anlegen("gast", "pw")
    h_gast = await _anmelden(client, "gast", "pw")
    r = await client.post("/api/v1/admin/benutzer", json={"name": "neu", "passwort": "pw"}, headers=h_gast)
    assert r.status_code == 403
    h_chef = await _anmelden(client)
    r = await client.post(
        "/api/v1/admin/benutzer", json={"name": "kind", "passwort": "pw", "rolle": "mitglied"},
        headers=h_chef,
    )
    assert r.status_code == 201

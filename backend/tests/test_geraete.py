"""Gekoppelte Geräte: Code am Rechner, Einlösen ohne Anmeldung, Schlüssel wie eine Sitzung (auch für den Lese-Cookie),
einmal gültig, ablaufend, ersetzt, gebremst, umbenennen, trennen, fremde Konten, gesperrtes Konto, Aufräumen."""

import httpx
import pytest

from app.main import app_bauen
from module.auth.dienst import AuthDienst
from module.geraete.dienst import Bremse, GeraeteDienst
from module.speicher.dienst import SpeicherDienst
from module.suche.dienst import SuchDienst
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
    app.state.geraete = GeraeteDienst(pool)
    await app.state.auth.benutzer_anlegen("chef", "geheim")
    await app.state.auth.benutzer_anlegen("gast", "geheim2")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        yield client, app


async def _anmelden(client, kennung="chef", passwort="geheim"):
    r = await client.post("/api/v1/auth/login", json={"kennung": kennung, "passwort": passwort})
    return {"X-Kellerwolke-Sitzung": r.json()["token"]}


async def _koppeln(client, code, name="Telefon", art="webapp"):
    return await client.post("/api/v1/geraete/koppeln", json={"code": code, "name": name, "art": art})


async def _gekoppelt(client, h):
    k = (await client.post("/api/v1/geraete/kopplung", headers=h)).json()
    r = await _koppeln(client, k["code"])
    return k, r.json(), {"X-Kellerwolke-Sitzung": r.json()["schluessel"]}


async def test_koppeln_und_mit_dem_schluessel_arbeiten(umgebung):
    client, app = umgebung
    h = await _anmelden(client)
    k = (await client.post("/api/v1/geraete/kopplung", headers=h)).json()
    assert k["stand"] == "wartet" and len(k["code"]) == 8
    assert (await client.get(f"/api/v1/geraete/kopplung/{k['id']}", headers=h)).json()["code"] is None
    # getippt wie angezeigt: mit Leerzeichen und klein
    r = await _koppeln(client, f"{k['code'][:4].lower()} {k['code'][4:]}")
    assert r.status_code == 201
    antwort = r.json()
    assert antwort["schluessel"].startswith("kw_geraet_") and antwort["benutzer"]["name"] == "chef"
    assert antwort["geraet"]["dieses"] and antwort["geraet"]["zuletzt_adresse"]
    hg = {"X-Kellerwolke-Sitzung": antwort["schluessel"]}
    # Der Rechner sieht, dass es geklappt hat.
    stand = (await client.get(f"/api/v1/geraete/kopplung/{k['id']}", headers=h)).json()
    assert stand["stand"] == "gekoppelt" and stand["geraet"]["name"] == "Telefon"
    # Der Schlüssel gilt wie eine Sitzung: Status, Dateien, Lese-Cookie für Inhaltsadressen.
    assert (await client.get("/api/v1/auth/status", headers=hg)).json()["benutzer"]["name"] == "chef"
    datei = (await client.post("/api/v1/dateien/upload", files={"datei": ("notiz.txt", b"vom Telefon")},
                               headers=hg)).json()
    assert (await client.post("/api/v1/inhalt/zugang", headers=hg)).status_code == 204
    r = await client.get(f"/api/v1/inhalt/datei/{datei['id']}")
    assert r.status_code == 200 and r.content == b"vom Telefon"
    # Dieses Gerät kennt sich; die Anmeldung mit Passwort ist keines.
    assert (await client.get("/api/v1/geraete/dieses", headers=hg)).json()["id"] == antwort["geraet"]["id"]
    assert (await client.get("/api/v1/geraete/dieses", headers=h)).status_code == 404
    liste = (await client.get("/api/v1/geraete", headers=hg)).json()
    assert [(g["name"], g["art"], g["dieses"]) for g in liste] == [("Telefon", "webapp", True)]
    assert [g["dieses"] for g in (await client.get("/api/v1/geraete", headers=h)).json()] == [False]


async def test_code_gilt_einmal_und_nicht_abgelaufen(umgebung):
    client, app = umgebung
    h = await _anmelden(client)
    k, _, _ = await _gekoppelt(client, h)
    assert (await _koppeln(client, k["code"])).status_code == 404            # schon eingelöst
    k2 = (await client.post("/api/v1/geraete/kopplung", headers=h)).json()
    async with app.state.pool.connection() as conn:
        await conn.execute("UPDATE kopplung SET ablauf = now() - interval '1 second' WHERE id=%s", (k2["id"],))
    assert (await client.get(f"/api/v1/geraete/kopplung/{k2['id']}", headers=h)).json()["stand"] == "abgelaufen"
    assert (await _koppeln(client, k2["code"])).status_code == 404


async def test_neuer_code_ersetzt_den_offenen_und_abbrechen(umgebung):
    client, app = umgebung
    h = await _anmelden(client)
    alt = (await client.post("/api/v1/geraete/kopplung", headers=h)).json()
    neu = (await client.post("/api/v1/geraete/kopplung", headers=h)).json()
    assert (await client.get(f"/api/v1/geraete/kopplung/{alt['id']}", headers=h)).status_code == 404
    assert (await _koppeln(client, alt["code"])).status_code == 404
    assert (await client.delete(f"/api/v1/geraete/kopplung/{neu['id']}", headers=h)).status_code == 204
    assert (await _koppeln(client, neu["code"])).status_code == 404


async def test_bremse_nach_falschen_codes(umgebung):
    client, app = umgebung
    h = await _anmelden(client)
    k = (await client.post("/api/v1/geraete/kopplung", headers=h)).json()
    for _ in range(Bremse.VERSUCHE):
        assert (await _koppeln(client, "AAAAAAAA")).status_code == 404
    r = await _koppeln(client, k["code"])                                     # auch der richtige wartet
    assert r.status_code == 429 and int(r.headers["retry-after"]) > 0
    app.state.geraete.bremse._gesperrt.clear()
    assert (await _koppeln(client, k["code"])).status_code == 201


async def test_eingaben_pruefen(umgebung):
    client, app = umgebung
    h = await _anmelden(client)
    k = (await client.post("/api/v1/geraete/kopplung", headers=h)).json()
    assert (await _koppeln(client, k["code"], name="  ")).status_code == 422
    assert (await _koppeln(client, k["code"], art="toaster")).status_code == 422
    assert (await _koppeln(client, k["code"], name="x" * 61)).status_code == 422
    assert (await _koppeln(client, k["code"], name="Tablet Küche", art="browser")).status_code == 201


async def test_umbenennen_trennen_und_abmelden(umgebung):
    client, app = umgebung
    h = await _anmelden(client)
    _, eins, h1 = await _gekoppelt(client, h)
    _, zwei, h2 = await _gekoppelt(client, h)
    gid = eins["geraet"]["id"]
    r = await client.patch(f"/api/v1/geraete/{gid}", json={"name": "Tablet Küche"}, headers=h)
    assert r.json()["name"] == "Tablet Küche"
    assert (await client.delete(f"/api/v1/geraete/{gid}", headers=h)).status_code == 204
    assert (await client.get("/api/v1/dateien", headers=h1)).status_code == 401   # sofort weg
    assert (await client.get("/api/v1/dateien", headers=h2)).status_code == 200
    # Abmelden auf dem Gerät selbst trennt es.
    assert (await client.post("/api/v1/auth/logout", headers=h2)).status_code == 204
    assert (await client.get("/api/v1/dateien", headers=h2)).status_code == 401
    assert (await client.get("/api/v1/geraete", headers=h)).json() == []
    assert (await client.get("/api/v1/dateien", headers=h)).status_code == 200     # die Sitzung bleibt


async def test_fremde_konten_und_gesperrtes_konto(umgebung):
    client, app = umgebung
    h = await _anmelden(client)
    hg = await _anmelden(client, "gast", "geheim2")
    k, antwort, hgeraet = await _gekoppelt(client, h)
    gid = antwort["geraet"]["id"]
    assert (await client.get("/api/v1/geraete", headers=hg)).json() == []
    assert (await client.get(f"/api/v1/geraete/kopplung/{k['id']}", headers=hg)).status_code == 404
    assert (await client.patch(f"/api/v1/geraete/{gid}", json={"name": "x"}, headers=hg)).status_code == 404
    assert (await client.delete(f"/api/v1/geraete/{gid}", headers=hg)).status_code == 404
    chef = next(b for b in await app.state.auth.liste_benutzer() if b["name"] == "chef")
    await app.state.auth.benutzer_aktualisieren(chef["id"], aktiv=False)
    assert (await client.get("/api/v1/dateien", headers=hgeraet)).status_code == 401
    k2 = (await client.post("/api/v1/geraete/kopplung", headers=hg)).json()
    gast = next(b for b in await app.state.auth.liste_benutzer() if b["name"] == "gast")
    await app.state.auth.benutzer_aktualisieren(gast["id"], aktiv=False)
    assert (await _koppeln(client, k2["code"])).status_code == 404              # Code eines gesperrten Kontos


async def test_aufraeumen_entfernt_alte_codes(umgebung):
    client, app = umgebung
    h = await _anmelden(client)
    k, _, hgeraet = await _gekoppelt(client, h)
    offen = (await client.post("/api/v1/geraete/kopplung", headers=h)).json()
    async with app.state.pool.connection() as conn:
        await conn.execute("UPDATE kopplung SET ablauf = now() - interval '2 hours' WHERE id=%s", (k["id"],))
    assert await app.state.geraete.aufraeumen() == 1
    assert (await client.get(f"/api/v1/geraete/kopplung/{k['id']}", headers=h)).status_code == 404
    assert (await client.get(f"/api/v1/geraete/kopplung/{offen['id']}", headers=h)).status_code == 200
    assert (await client.get("/api/v1/dateien", headers=hgeraet)).status_code == 200   # Gerät bleibt

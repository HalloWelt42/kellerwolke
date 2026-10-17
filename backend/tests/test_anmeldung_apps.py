"""Anmeldung an eigenen Apps nur zur Erkennung (Nutzer, 17.10.2026: kein Dauerrecht über das ganze Konto).

Eine Sitzung oder ein Geräteschlüssel für eine App taugt für Status, Abmelden und, zusammen mit dem App-Schlüssel
derselben App, für die Dateiwahl; an Dateien kommt sie nicht.
"""

from tests.test_ablage import datei, ordner, umgebung, zugang  # noqa: F401 (Fixture)
from tests.test_anfragen import AKTIONEN


async def _app_sitzung(client, app="Transkription") -> dict:
    r = await client.post("/api/v1/auth/login", json={"kennung": "chef", "passwort": "geheim", "fuer_app": app})
    assert r.status_code == 200, r.text
    return {"X-Kellerwolke-Sitzung": r.json()["token"]}


async def test_sitzung_einer_app_kommt_nicht_an_dateien(umgebung):
    client, sitzung = umgebung
    o = await ordner(client, sitzung, "Privat")
    d = await datei(client, sitzung, "Brief.md", b"geheim", o)
    app = await _app_sitzung(client)
    status = (await client.get("/api/v1/auth/status", headers=app)).json()
    assert status["angemeldet"] and status["app"] == "Transkription" and status["benutzer"]["name"] == "chef"
    assert (await client.get("/api/v1/dateien", headers=app)).status_code == 403
    assert (await client.get(f"/api/v1/dateien/{d}/inhalt", headers=app)).status_code == 403
    assert (await client.get(f"/api/v1/inhalt/datei/{d}", headers=app)).status_code == 403
    assert (await client.get("/api/v1/app-zugaenge", headers=app)).status_code == 403
    # die eigene Anmeldung der Kellerwolke bleibt wie sie war
    assert (await client.get("/api/v1/auth/status", headers=sitzung)).json()["app"] is None
    assert (await client.get("/api/v1/dateien", headers=sitzung)).status_code == 200
    assert (await client.post("/api/v1/auth/logout", headers=app)).status_code == 204
    assert (await client.get("/api/v1/auth/status", headers=app)).json()["angemeldet"] is False


async def test_geraet_fuer_eine_app_kommt_nicht_an_dateien(umgebung):
    client, sitzung = umgebung
    code = (await client.post("/api/v1/geraete/kopplung", headers=sitzung)).json()["code"]
    r = await client.post("/api/v1/geraete/koppeln", json={"code": code, "name": "iPhone", "art": "webapp",
                                                           "fuer_app": "Transkription"})
    assert r.status_code == 201, r.text
    geraet = {"X-Kellerwolke-Sitzung": r.json()["schluessel"]}
    assert (await client.get("/api/v1/auth/status", headers=geraet)).json()["app"] == "Transkription"
    assert (await client.get("/api/v1/dateien", headers=geraet)).status_code == 403
    liste = (await client.get("/api/v1/geraete", headers=sitzung)).json()
    assert [(g["name"], g["app"]) for g in liste] == [("iPhone", "Transkription")]


async def test_dateiwahl_braucht_schluessel_und_anmeldung_derselben_app(umgebung):
    client, sitzung = umgebung
    _, kopf = await zugang(client, sitzung, "Transkription")
    await client.put("/api/v1/ablage/aktionen", json=AKTIONEN, headers=kopf)
    o = await ordner(client, sitzung, "Besprechungen")
    ton = await datei(client, sitzung, "Runde.wav", b"RIFF-ton", o)
    app = await _app_sitzung(client)

    beide = {**kopf, **app}
    wurzel = (await client.get("/api/v1/ablage/wahl", headers=beide)).json()
    assert [k["name"] for k in wurzel["kette"]] == ["Meine Dateien"]
    assert "Besprechungen" in [e["name"] for e in wurzel["eintraege"]]
    seite = (await client.get("/api/v1/ablage/wahl", params={"ordner": o}, headers=beide)).json()
    assert [k["name"] for k in seite["kette"]] == ["Meine Dateien", "Besprechungen"]
    assert [(e["name"], e["inhaltstyp"]) for e in seite["eintraege"]] == [("Runde.wav", "audio/wav")]

    # ohne Anmeldung, mit der Sitzung der Kellerwolke oder der einer anderen App: keine Wahl
    assert (await client.get("/api/v1/ablage/wahl", headers=kopf)).status_code == 401
    assert (await client.get("/api/v1/ablage/wahl", headers={**kopf, **sitzung})).status_code == 403
    andere = await _app_sitzung(client, "Stimmenausgabe")
    assert (await client.get("/api/v1/ablage/wahl", headers={**kopf, **andere})).status_code == 403

    # die Wahl stellt eine Anfrage an diese App; erst dann darf sie die Datei lesen
    assert (await client.get(f"/api/v1/ablage/knoten/{ton}/inhalt", headers=kopf)).status_code == 404
    r = await client.post("/api/v1/ablage/wahl", json={"knoten_id": ton, "aktion": "transkribieren"}, headers=beide)
    assert r.status_code == 200, r.text
    anfrage = r.json()["anfrage"]
    assert anfrage["app"] == "Transkription" and anfrage["zustand"] == "wartet"
    mit = {**kopf, "X-Kellerwolke-Anfrage": anfrage["id"]}
    assert (await client.get(f"/api/v1/ablage/knoten/{ton}/inhalt", headers=mit)).content == b"RIFF-ton"

"""Kernwege, die die Oberfläche braucht: lesbare Prüfmeldungen, Suche mit Favorit über Namen von Dateien und
Ordnern, Journal-Stand als Startpunkt, Eintrag beim endgültigen Löschen, Ordnerkette eines Knotens."""

from module.suche.dienst import SuchDienst
from tests.test_api import _anmelden, _upload, umgebung  # noqa: F401 - Fixture


async def test_pruefmeldung_ist_lesbar(umgebung):
    client, _ = umgebung
    h = await _anmelden(client)
    r = await client.post("/api/v1/dateien/ordner", json={"name": "a/b"}, headers=h)
    assert r.status_code == 422
    assert isinstance(r.json()["detail"], str) and r.json()["detail"].startswith("Name: ")
    r = await client.post("/api/v1/dateien/ordner", json={}, headers=h)
    assert r.json()["detail"] == "Name: fehlt"
    r = await client.get("/api/v1/dateien?parent_id=kein-uuid", headers=h)
    assert r.json()["detail"] == "Zielordner: keine gültige Kennung"


async def test_suche_findet_ordner_umbenanntes_und_meldet_favorit(umgebung):
    client, app = umgebung
    app.state.suche = SuchDienst(app.state.pool)
    h = await _anmelden(client)
    ordner = (await client.post("/api/v1/dateien/ordner", json={"name": "Steuern 2026"}, headers=h)).json()
    datei = (await _upload(client, h, "a.txt", b"nichts")).json()
    await client.patch(f"/api/v1/dateien/{datei['id']}/name", json={"name": "Rechnung.txt"}, headers=h)
    await client.post(f"/api/v1/dateien/{datei['id']}/favorit", headers=h)

    treffer = (await client.get("/api/v1/suche", params={"q": "Rechnung"}, headers=h)).json()
    assert [t["id"] for t in treffer] == [datei["id"]] and treffer[0]["favorit"] is True
    assert (await client.get("/api/v1/suche", params={"q": "a"}, headers=h)).json() == []
    treffer = (await client.get("/api/v1/suche", params={"q": "steuern"}, headers=h)).json()
    assert [t["id"] for t in treffer] == [ordner["id"]] and treffer[0]["favorit"] is False


async def test_journal_stand_und_entfernt(umgebung):
    client, _ = umgebung
    h = await _anmelden(client)
    assert (await client.get("/api/v1/sync/stand", headers=h)).json() == {"seq": 0}
    k = (await _upload(client, h, "weg.txt", b"x")).json()
    await client.delete(f"/api/v1/dateien/{k['id']}", headers=h)
    stand = (await client.get("/api/v1/sync/stand", headers=h)).json()["seq"]
    assert stand == 2
    assert (await client.delete(f"/api/v1/dateien/{k['id']}/endgueltig", headers=h)).status_code == 204
    neu = (await client.get("/api/v1/sync/journal", params={"seit": stand}, headers=h)).json()
    assert [(e["typ"], e["knoten_id"]) for e in neu] == [("entfernt", k["id"])]


async def test_pfad_eines_knotens(umgebung):
    client, app = umgebung
    h = await _anmelden(client)
    a = (await client.post("/api/v1/dateien/ordner", json={"name": "A"}, headers=h)).json()
    b = (await client.post("/api/v1/dateien/ordner", json={"name": "B", "parent_id": a["id"]}, headers=h)).json()
    r = await client.post("/api/v1/dateien/upload", data={"parent_id": b["id"]},
                          files={"datei": ("x.txt", b"x", "text/plain")}, headers=h)
    x = r.json()
    assert (await client.get(f"/api/v1/dateien/{x['id']}/pfad", headers=h)).json() == [
        {"id": a["id"], "name": "A"}, {"id": b["id"], "name": "B"}]
    assert (await client.get(f"/api/v1/dateien/{a['id']}/pfad", headers=h)).json() == []
    await app.state.auth.benutzer_anlegen("fremd", "geheim3")
    hf = await _anmelden(client, "fremd", "geheim3")
    assert (await client.get(f"/api/v1/dateien/{x['id']}/pfad", headers=hf)).status_code == 404

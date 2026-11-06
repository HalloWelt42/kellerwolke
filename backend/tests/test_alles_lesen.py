"""Alles lesen (KW-3): Ein App-Zugang darf auf Wunsch jede Datei seines Kontos lesen, die oberste Ebene auflisten, in
der ganzen Wolke suchen und den Text einer Datei holen. Schreiben bleibt bei den Rechten je Ordner, fremde Konten bleiben
unsichtbar, ohne die Freigabe gilt alles wie bisher."""

from tests.test_ablage import datei, ordner, umgebung, zugang  # noqa: F401 (Fixture)


async def _freigabe(client, sitzung, zugang_id: str, an: bool) -> dict:
    r = await client.patch(f"/api/v1/app-zugaenge/{zugang_id}", json={"alles_lesen": an}, headers=sitzung)
    assert r.status_code == 200, r.text
    return r.json()


async def test_ohne_freigabe_wie_bisher(umgebung):
    client, sitzung = umgebung
    privat = await ordner(client, sitzung, "Privat")
    brief = await datei(client, sitzung, "brief.txt", b"Mietvertrag Kuendigung", privat)
    z, kopf = await zugang(client, sitzung, "Assistent")
    assert z["alles_lesen"] is False
    assert (await client.get(f"/api/v1/ablage/knoten/{brief}", headers=kopf)).status_code == 404
    assert (await client.get(f"/api/v1/ablage/knoten/{brief}/text", headers=kopf)).status_code == 404
    assert (await client.get("/api/v1/ablage/wurzel/kinder", headers=kopf)).status_code == 403
    assert (await client.post("/api/v1/ablage/volltext", json={"q": "brief"}, headers=kopf)).status_code == 403


async def test_mit_freigabe_alles_lesbar_aber_nicht_schreibbar(umgebung):
    client, sitzung = umgebung
    privat = await ordner(client, sitzung, "Privat")
    brief = await datei(client, sitzung, "brief.txt", b"Mietvertrag: Kuendigungsfrist drei Monate", privat)
    z, kopf = await zugang(client, sitzung, "Assistent")
    assert (await _freigabe(client, sitzung, z["id"], True))["alles_lesen"] is True

    k = (await client.get(f"/api/v1/ablage/knoten/{brief}", headers=kopf)).json()
    assert (k["pfad"], k["recht"]) == ("Privat/brief.txt", "lesen")
    text = (await client.get(f"/api/v1/ablage/knoten/{brief}/text", headers=kopf)).json()
    assert text["lesbar"] and "drei Monate" in text["text"] and not text["gekuerzt"]
    kurz = (await client.get(f"/api/v1/ablage/knoten/{brief}/text?grenze=10", headers=kopf)).json()
    assert len(kurz["text"]) == 10 and kurz["gekuerzt"]
    # Schreiben bleibt verboten (nur lesen), im eigenen Ordner der App geht es weiter
    r = await client.put("/api/v1/ablage/datei", params={"pfad": "Privat/neu.txt"}, content=b"x", headers=kopf)
    assert r.status_code in (403, 404), r.text
    r = await client.put("/api/v1/ablage/datei", params={"pfad": "Apps/Assistent/notiz.txt"}, content=b"x", headers=kopf)
    assert r.status_code == 200, r.text

    wurzel = (await client.get("/api/v1/ablage/wurzel/kinder", headers=kopf)).json()
    namen = {w["name"]: w["recht"] for w in wurzel}
    assert namen["Privat"] == "lesen" and namen["Apps"] == "lesen"

    treffer = (await client.post("/api/v1/ablage/volltext", json={"q": "brief"}, headers=kopf)).json()
    assert [(t["pfad"], t["im_namen"], t["recht"]) for t in treffer] == [("Privat/brief.txt", True, "lesen")]

    # Abschalten nimmt alles wieder weg
    await _freigabe(client, sitzung, z["id"], False)
    assert (await client.get(f"/api/v1/ablage/knoten/{brief}", headers=kopf)).status_code == 404


async def test_fremde_konten_bleiben_unsichtbar(umgebung):
    client, sitzung = umgebung
    r = await client.post("/api/v1/auth/login", json={"kennung": "gast", "passwort": "geheim"})
    gast = {"X-Kellerwolke-Sitzung": r.json()["token"]}
    fremd = await datei(client, gast, "gast-brief.txt", b"geheim", None)
    z, kopf = await zugang(client, sitzung, "Assistent")
    await _freigabe(client, sitzung, z["id"], True)
    assert (await client.get(f"/api/v1/ablage/knoten/{fremd}", headers=kopf)).status_code == 404
    assert (await client.get(f"/api/v1/ablage/knoten/{fremd}/text", headers=kopf)).status_code == 404
    assert (await client.post("/api/v1/ablage/volltext", json={"q": "gast"}, headers=kopf)).json() == []
    assert "gast-brief.txt" not in {w["name"] for w in (await client.get("/api/v1/ablage/wurzel/kinder", headers=kopf)).json()}


async def test_text_nur_fuer_dateien_und_bilder_ohne_text(umgebung):
    client, sitzung = umgebung
    privat = await ordner(client, sitzung, "Privat")
    bild = await datei(client, sitzung, "foto.jpg", b"\xff\xd8\xff\xe0kein echtes bild", privat)
    z, kopf = await zugang(client, sitzung, "Assistent")
    await _freigabe(client, sitzung, z["id"], True)
    assert (await client.get(f"/api/v1/ablage/knoten/{privat}/text", headers=kopf)).status_code == 422
    t = (await client.get(f"/api/v1/ablage/knoten/{bild}/text", headers=kopf)).json()
    assert t["lesbar"] is False and t["text"] == ""

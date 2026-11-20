"""Verweise (KW-10): eine Datei gibt es genau einmal, andere Ordner zeigen nur auf sie.

Szenario der Telegram-Ablage: die Bildablage (App ImageVault) hält das Bild, die Telegram-App legt in ihrem Chat-Ordner
einen Verweis an. Geprüft werden Anlegen mit Rechten, Lesen über das Ziel, Löschen mit Folgen, Papierkorb hin und
zurück, verwaiste Verweise, Suche ohne Doppel und WebDAV nur lesend; dazu die Prüfsumme (KW-11).
"""

import base64
import hashlib

from tests.test_ablage import datei, ordner, umgebung, zugang  # noqa: F401 (umgebung ist die Fixture)

BILD = b"\xff\xd8\xff" + b"Torte mit Kerzen" * 400


async def _aufbau(client, sitzung):
    """ImageVault schreibt ein Bild, Telegram bekommt einen Chat-Ordner; liefert (bild, iv_kopf, tg_kopf, chat_pfad)."""
    _, iv = await zugang(client, sitzung, "ImageVault")
    _, tg = await zugang(client, sitzung, "Telegram")
    r = await client.post("/api/v1/ablage/ordner", json={"pfad": "Apps/ImageVault/2026/11"}, headers=iv)
    assert r.status_code == 200, r.text
    r = await client.put("/api/v1/ablage/datei", params={"pfad": "Apps/ImageVault/2026/11/IMG_4711.jpg"}, content=BILD,
                         headers={**iv, "Content-Type": "image/jpeg"})
    assert r.status_code == 200, r.text
    bild = r.json()
    r = await client.post("/api/v1/ablage/ordner", json={"pfad": "Apps/Telegram/Familie/2026-11"}, headers=tg)
    assert r.status_code == 200, r.text
    return bild, iv, tg, "Apps/Telegram/Familie/2026-11"


async def _verweis(client, kopf, ziel_id, pfad):
    return await client.post("/api/v1/ablage/verweis", json={"ziel_id": ziel_id, "pfad": pfad}, headers=kopf)


async def test_verweis_anlegen_und_lesen_folgt_dem_ziel(umgebung):
    client, sitzung = umgebung
    bild, _, tg, chat = await _aufbau(client, sitzung)
    r = await _verweis(client, tg, bild["id"], f"{chat}/2026-11-03 Oma.jpg")
    assert r.status_code == 200, r.text
    v = r.json()
    assert v["typ"] == "verweis" and v["ziel_id"] == bild["id"] and not v["verwaist"]
    assert v["groesse"] == len(BILD) and v["sha256"] == hashlib.sha256(BILD).hexdigest() == bild["sha256"]
    assert v["etag"] == bild["etag"] and v["inhaltstyp"] == "image/jpeg" and v["app"] == "Telegram"

    r = await client.get(f"/api/v1/ablage/knoten/{v['id']}/inhalt", headers=tg)
    assert r.status_code == 200 and r.content == BILD and r.headers["etag"].strip('"') == bild["etag"]
    versionen = (await client.get(f"/api/v1/ablage/knoten/{v['id']}/versionen", headers=tg)).json()
    assert [x["sha256"] for x in versionen] == [bild["sha256"]] and versionen[0]["aktuell"]

    # derselbe Aufruf noch einmal legt nichts doppelt an; ein Verweis auf den Verweis zeigt aufs Original
    assert (await _verweis(client, tg, bild["id"], f"{chat}/2026-11-03 Oma.jpg")).json()["id"] == v["id"]
    kette = (await _verweis(client, tg, v["id"], f"{chat}/noch einmal.jpg")).json()
    assert kette["ziel_id"] == bild["id"]

    # Oberfläche: Liste mit Kennzeichen, das Original zählt seine Verweise
    eltern = (await client.get("/api/v1/dateien/aufloesen", params={"pfad": chat}, headers=sitzung)).json()
    liste = (await client.get("/api/v1/dateien", params={"parent_id": eltern["id"]}, headers=sitzung)).json()
    eintrag = next(k for k in liste if k["id"] == v["id"])
    assert eintrag["typ"] == "verweis" and eintrag["ziel_name"] == "IMG_4711.jpg" and eintrag["medienart"] == "bild"
    assert eintrag["etag"] == bild["etag"] and eintrag["groesse"] == len(BILD)
    original = (await client.get("/api/v1/dateien", params={"parent_id": bild["parent_id"]}, headers=sitzung)).json()
    assert original[0]["verweis_anzahl"] == 2 and original[0]["sha256"] == bild["sha256"]
    r = await client.get(f"/api/v1/dateien/{v['id']}/inhalt", headers=sitzung)
    assert r.status_code == 200 and r.content == BILD
    am_original = (await client.get(f"/api/v1/dateien/{bild['id']}/verweise", headers=sitzung)).json()
    assert {(x["name"], x["ort"], x["app"]) for x in am_original} == {
        ("2026-11-03 Oma.jpg", chat, "Telegram"), ("noch einmal.jpg", chat, "Telegram")}


async def test_verweis_nur_im_eigenen_zweig_nur_auf_lesbare_dateien(umgebung):
    client, sitzung = umgebung
    bild, iv, tg, chat = await _aufbau(client, sitzung)
    # nicht im Ordner einer anderen App (dort nur lesen)
    assert (await _verweis(client, tg, bild["id"], "Apps/ImageVault/2026/11/Kopie.jpg")).status_code == 403
    # nicht auf eine Datei außerhalb der Leserechte (sie gibt es für die App nicht)
    privat = await ordner(client, sitzung, "Privat")
    geheim = await datei(client, sitzung, "Tagebuch.txt", b"geheim", privat)
    assert (await _verweis(client, tg, geheim, f"{chat}/Tagebuch.txt")).status_code == 404
    # nur auf Dateien, nicht auf Ordner; ein Verweis ist nicht beschreibbar
    assert (await _verweis(client, tg, bild["parent_id"], f"{chat}/Ordner")).status_code == 422
    v = (await _verweis(client, tg, bild["id"], f"{chat}/Oma.jpg")).json()
    r = await client.put("/api/v1/ablage/datei", params={"pfad": f"{chat}/Oma.jpg"}, content=b"neu",
                         headers={**tg, "If-Match": v["etag"]})
    assert r.status_code == 409 and "Verweis" in r.json()["detail"]
    r = await client.put(f"/api/v1/ablage/knoten/{v['id']}/inhalt", content=b"neu", headers={**tg, "If-Match": v["etag"]})
    assert r.status_code == 409
    # ein belegter Name weist ab
    await client.put("/api/v1/ablage/datei", params={"pfad": f"{chat}/Notiz.txt"}, content=b"x", headers=tg)
    assert (await _verweis(client, tg, bild["id"], f"{chat}/Notiz.txt")).status_code == 409


async def test_verweis_loeschen_nimmt_nur_den_verweis(umgebung):
    client, sitzung = umgebung
    bild, iv, tg, chat = await _aufbau(client, sitzung)
    v = (await _verweis(client, tg, bild["id"], f"{chat}/Oma.jpg")).json()
    folgen = (await client.post("/api/v1/dateien/loeschfolgen", json={"ids": [v["id"]]}, headers=sitzung)).json()
    assert folgen == {"folgen": []}
    assert (await client.delete(f"/api/v1/ablage/knoten/{v['id']}", headers=tg)).status_code == 204
    r = await client.get(f"/api/v1/ablage/knoten/{bild['id']}/inhalt", headers=iv)
    assert r.status_code == 200 and r.content == BILD
    korb = (await client.get("/api/v1/dateien/papierkorb", headers=sitzung)).json()
    assert [(k["name"], k["typ"]) for k in korb] == [("Oma.jpg", "verweis")]


async def test_original_loeschen_zeigt_folgen_und_alles_kommt_gemeinsam_zurueck(umgebung):
    client, sitzung = umgebung
    bild, iv, tg, chat = await _aufbau(client, sitzung)
    v = (await _verweis(client, tg, bild["id"], f"{chat}/Oma.jpg")).json()
    r = await client.put(f"/api/v1/ablage/knoten/{bild['id']}/begleiter/beschreibung",
                         params={"zusatz": ".beschreibung.json"}, content=b"{}", headers=iv)
    assert r.status_code == 200, r.text
    begleiter = r.json()

    folgen = (await client.post("/api/v1/dateien/loeschfolgen", json={"ids": [bild["id"]]}, headers=sitzung)).json()
    assert {(f["art"], f["name"], f["ort"]) for f in folgen["folgen"]} == {
        ("verweis", "Oma.jpg", chat), ("begleiter", "IMG_4711.beschreibung.json", "Apps/ImageVault/2026/11")}
    app_sicht = (await client.get(f"/api/v1/ablage/knoten/{bild['id']}/loeschfolgen", headers=iv)).json()
    assert {f["pfad"] for f in app_sicht["folgen"]} == {f"{chat}/Oma.jpg",
                                                         "Apps/ImageVault/2026/11/IMG_4711.beschreibung.json"}
    assert app_sicht["verborgen"] == 0

    assert (await client.delete(f"/api/v1/dateien/{bild['id']}", headers=sitzung)).status_code == 204
    assert (await client.get(f"/api/v1/ablage/knoten/{v['id']}", headers=tg)).status_code == 404
    korb = (await client.get("/api/v1/dateien/papierkorb", headers=sitzung)).json()
    assert [(k["name"], k["verweis_anzahl"], k["begleiter_anzahl"]) for k in korb] == [("IMG_4711.jpg", 1, 1)]
    app_korb = (await client.get("/api/v1/ablage/papierkorb", params={"ordner": bild["parent_id"]}, headers=iv)).json()
    assert [x["name"] for x in app_korb[0]["verweise"]] == ["Oma.jpg"]

    # Inzwischen liegt unter dem Namen etwas anderes: der Verweis kommt mit Zusatz zurück
    await client.put("/api/v1/ablage/datei", params={"pfad": f"{chat}/Oma.jpg"}, content=b"anders", headers=tg)
    r = await client.post(f"/api/v1/dateien/{bild['id']}/wiederherstellen", headers=sitzung)
    assert r.status_code == 200, r.text
    zurueck = (await client.get(f"/api/v1/ablage/knoten/{v['id']}", headers=tg)).json()
    assert zurueck["pfad"] == f"{chat}/Oma (wiederhergestellt).jpg" and not zurueck["verwaist"]
    assert (await client.get(f"/api/v1/ablage/knoten/{begleiter['id']}", headers=iv)).status_code == 200


async def test_ordner_loeschen_nimmt_verweise_von_aussen_mit(umgebung):
    client, sitzung = umgebung
    bild, iv, tg, chat = await _aufbau(client, sitzung)
    v = (await _verweis(client, tg, bild["id"], f"{chat}/Oma.jpg")).json()
    jahr = (await client.get("/api/v1/ablage/pfad", params={"pfad": "Apps/ImageVault/2026"}, headers=iv)).json()
    folgen = (await client.post("/api/v1/dateien/loeschfolgen", json={"ids": [jahr["id"]]}, headers=sitzung)).json()
    assert [(f["art"], f["zu_name"]) for f in folgen["folgen"]] == [("verweis", "IMG_4711.jpg")]
    await client.delete(f"/api/v1/dateien/{jahr['id']}", headers=sitzung)
    assert (await client.get(f"/api/v1/ablage/knoten/{v['id']}", headers=tg)).status_code == 404
    # liegt der Ordner des Verweises inzwischen selbst im Papierkorb, kommt er nach "Meine Dateien"
    familie = (await client.get("/api/v1/ablage/pfad", params={"pfad": "Apps/Telegram/Familie"}, headers=tg)).json()
    await client.delete(f"/api/v1/dateien/{familie['id']}", headers=sitzung)
    assert (await client.post(f"/api/v1/dateien/{jahr['id']}/wiederherstellen", headers=sitzung)).status_code == 200
    oben = (await client.get("/api/v1/dateien", headers=sitzung)).json()
    assert any(k["id"] == v["id"] and k["typ"] == "verweis" and not k["verwaist"] for k in oben)


async def test_endgueltig_loeschen_nimmt_verweise_mit_und_allein_geloeschte_werden_verwaist(umgebung, pool):
    client, sitzung = umgebung
    bild, iv, tg, chat = await _aufbau(client, sitzung)
    mit = (await _verweis(client, tg, bild["id"], f"{chat}/mit.jpg")).json()
    allein = (await _verweis(client, tg, bild["id"], f"{chat}/allein.jpg")).json()
    await client.delete(f"/api/v1/ablage/knoten/{allein['id']}", headers=tg)     # vorher allein in den Papierkorb
    await client.delete(f"/api/v1/dateien/{bild['id']}", headers=sitzung)
    assert (await client.delete(f"/api/v1/dateien/{bild['id']}/endgueltig", headers=sitzung)).status_code == 204
    async with pool.connection() as conn:
        cur = await conn.execute("SELECT id FROM knoten WHERE id = ANY(%s)", ([mit["id"], allein["id"]],))
        assert [str(z[0]) for z in await cur.fetchall()] == [allein["id"]]
    # der allein gelöschte kommt verwaist zurück: sichtbar, ohne Inhalt, nur noch zu entfernen
    assert (await client.post(f"/api/v1/dateien/{allein['id']}/wiederherstellen", headers=sitzung)).status_code == 200
    k = (await client.get(f"/api/v1/ablage/knoten/{allein['id']}", headers=tg)).json()
    assert k["verwaist"] and k["ziel_id"] is None and k["groesse"] is None and k["inhaltstyp"] is None
    assert (await client.get(f"/api/v1/ablage/knoten/{allein['id']}/inhalt", headers=tg)).status_code == 404
    assert (await client.get(f"/api/v1/dateien/{allein['id']}/inhalt", headers=sitzung)).status_code == 404
    assert (await client.delete(f"/api/v1/ablage/knoten/{allein['id']}", headers=tg)).status_code == 204


async def test_original_im_papierkorb_macht_allein_geholte_verweise_verwaist(umgebung):
    client, sitzung = umgebung
    bild, iv, tg, chat = await _aufbau(client, sitzung)
    v = (await _verweis(client, tg, bild["id"], f"{chat}/Oma.jpg")).json()
    await client.delete(f"/api/v1/ablage/knoten/{v['id']}", headers=tg)
    await client.delete(f"/api/v1/dateien/{bild['id']}", headers=sitzung)
    await client.post(f"/api/v1/dateien/{v['id']}/wiederherstellen", headers=sitzung)
    assert (await client.get(f"/api/v1/ablage/knoten/{v['id']}", headers=tg)).json()["verwaist"]
    await client.post(f"/api/v1/dateien/{bild['id']}/wiederherstellen", headers=sitzung)
    assert not (await client.get(f"/api/v1/ablage/knoten/{v['id']}", headers=tg)).json()["verwaist"]


async def test_suche_zaehlt_verweise_nicht_doppelt(umgebung):
    client, sitzung = umgebung
    bild, iv, tg, chat = await _aufbau(client, sitzung)
    await _verweis(client, tg, bild["id"], f"{chat}/Kuchen IMG_4711.jpg")
    await _verweis(client, tg, bild["id"], f"{chat}/Geburtstag Kuchen.jpg")
    await _verweis(client, tg, bild["id"], f"{chat}/Kuchen nochmal.jpg")
    treffer = (await client.get("/api/v1/suche", params={"q": "IMG_4711"}, headers=sitzung)).json()
    assert [t["id"] for t in treffer] == [bild["id"]]                 # das Original trifft: kein Verweis daneben
    treffer = (await client.get("/api/v1/suche", params={"q": "Kuchen"}, headers=sitzung)).json()
    assert len(treffer) == 1 and treffer[0]["typ"] == "verweis"       # nur Verweise treffen: einer für das Original


async def test_pruefsumme_findet_nur_lesbares_und_keine_verweise(umgebung):
    client, sitzung = umgebung
    bild, iv, tg, chat = await _aufbau(client, sitzung)
    await _verweis(client, tg, bild["id"], f"{chat}/Oma.jpg")
    privat = await ordner(client, sitzung, "Privat")
    await datei(client, sitzung, "Kopie.jpg", BILD, privat)            # gleicher Inhalt, für die App unsichtbar
    sha = hashlib.sha256(BILD).hexdigest()
    treffer = (await client.get(f"/api/v1/ablage/pruefsumme/{sha}", headers=tg)).json()
    assert [(t["id"], t["pfad"], t["typ"]) for t in treffer] == [(bild["id"], "Apps/ImageVault/2026/11/IMG_4711.jpg", "datei")]
    assert (await client.get(f"/api/v1/ablage/pruefsumme/{'0' * 64}", headers=tg)).json() == []
    assert (await client.get("/api/v1/ablage/pruefsumme/nichtsha", headers=tg)).status_code == 422


async def test_webdav_zeigt_verweise_nur_lesend(umgebung):
    client, sitzung = umgebung
    bild, iv, tg, chat = await _aufbau(client, sitzung)
    await _verweis(client, tg, bild["id"], f"{chat}/Oma.jpg")
    basis = {"Authorization": "Basic " + base64.b64encode(b"chef:geheim").decode()}
    pfad = f"/webdav/{chat}/Oma.jpg"
    r = await client.request("PROPFIND", f"/webdav/{chat}/", headers={**basis, "Depth": "1"})
    assert r.status_code == 207 and "Oma.jpg" in r.text and f"<D:getcontentlength>{len(BILD)}<" in r.text
    r = await client.get(pfad, headers=basis)
    assert r.status_code == 200 and r.content == BILD
    assert (await client.put(pfad, content=b"neu", headers=basis)).status_code == 403
    assert (await client.request("DELETE", pfad, headers=basis)).status_code == 403
    r = await client.request("MOVE", pfad, headers={**basis, "Destination": f"/webdav/{chat}/Anders.jpg"})
    assert r.status_code == 403

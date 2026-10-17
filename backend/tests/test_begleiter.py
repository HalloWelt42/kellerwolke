"""Begleitdateien: Ergebnisse liegen neben ihrer Quelle und ziehen mit ihr um (Nutzer, 17.10.2026: "zusammengehörige
dateien immer beieinander ablegen, so geht nix verloren").

Geprüft werden alle Wege, auf denen sich eine Gruppe ändern kann: Apps über die Ablage, die Oberfläche (umbenennen,
verschieben, Papierkorb, wiederherstellen, endgültig löschen, lösen) und WebDAV.
"""

import pytest

from module.speicher import begleiter
from tests.test_ablage import datei, ordner, umgebung, zugang  # noqa: F401 (Fixture)

AUTH = ("chef", "geheim")


# --- Namen ------------------------------------------------------------------------------------------------------

def test_namen_und_stamm():
    assert begleiter.stamm("Besprechung.wav") == "Besprechung"
    assert begleiter.stamm("ohne") == "ohne"
    assert begleiter.stamm(".versteckt") == ".versteckt"
    assert begleiter.namen("Besprechung.wav", ".transkript.json") == [
        "Besprechung.transkript.json", "Besprechung.wav.transkript.json"]
    assert begleiter.namen("Besprechung.wav", ".srt") == ["Besprechung.srt", "Besprechung.wav.srt"]


def test_nachgezogen_folgt_dem_neuen_namen():
    assert begleiter.nachgezogen("A.wav", "B.mp3", "A.transkript.json") == "B.transkript.json"
    assert begleiter.nachgezogen("A.wav", "B.mp3", "A.wav.transkript.json") == "B.mp3.transkript.json"
    assert begleiter.nachgezogen("A.wav", "B.mp3", "Notiz.json") is None


def test_rolle_und_zusatz_werden_geprueft():
    with pytest.raises(ValueError):
        begleiter.rolle_pruefen("Transkript")
    for falsch in ("json", ".a.b.c.d", "./x", ".x y"):
        with pytest.raises(ValueError):
            begleiter.zusatz_pruefen(falsch)
    assert begleiter.zusatz_pruefen(".Transkript.JSON") == ".transkript.json"


# --- Hilfen -----------------------------------------------------------------------------------------------------

async def _app_mit_ton(client, sitzung):
    """App mit Zugang, im eigenen Ordner Apps/Transkription/Besprechungen liegt ein Ton."""
    z, kopf = await zugang(client, sitzung, "Transkription")
    eigen = next(r["knoten_id"] for r in z["rechte"] if r["pfad"] == "Apps/Transkription")
    unter = await ordner(client, sitzung, "Besprechungen", eigen)
    ton = await datei(client, sitzung, "Runde.wav", b"RIFF-ton", unter)
    return kopf, eigen, unter, ton


async def _schreiben(client, kopf, haupt, rolle="transkript", inhalt=b'{"a":1}', zusatz=".transkript.json", **koepfe):
    return await client.put(f"/api/v1/ablage/knoten/{haupt}/begleiter/{rolle}", params={"zusatz": zusatz},
                            content=inhalt, headers={**kopf, **koepfe, "Content-Type": "application/json"})


async def _namen(client, sitzung, parent_id) -> dict:
    r = await client.get("/api/v1/dateien", params={"parent_id": parent_id}, headers=sitzung)
    assert r.status_code == 200, r.text
    return {k["name"]: k for k in r.json()}


# --- Apps schreiben Begleiter -----------------------------------------------------------------------------------

async def test_app_schreibt_begleiter_neben_die_quelle(umgebung):
    client, sitzung = umgebung
    kopf, _, unter, ton = await _app_mit_ton(client, sitzung)
    r = await _schreiben(client, kopf, ton)
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["name"] == "Runde.transkript.json" and b["parent_id"] == unter
    assert b["haupt_id"] == ton and b["rolle"] == "transkript"
    # zweites Schreiben ohne gelesenen Stand wird abgewiesen, mit Stand gibt es eine neue Version
    assert (await _schreiben(client, kopf, ton, inhalt=b"{}")).status_code == 428
    r2 = await _schreiben(client, kopf, ton, inhalt=b'{"a":2}', **{"If-Match": b["etag"]})
    assert r2.status_code == 200 and r2.json()["id"] == b["id"]
    assert len((await client.get(f"/api/v1/ablage/knoten/{b['id']}/versionen", headers=kopf)).json()) == 2
    liste = (await client.get(f"/api/v1/ablage/knoten/{ton}/begleiter", headers=kopf)).json()
    assert [(x["name"], x["rolle"]) for x in liste] == [("Runde.transkript.json", "transkript")]
    herkunft = (await client.get(f"/api/v1/ablage/knoten/{b['id']}/herkunft", headers=kopf)).json()
    assert [(h["von_id"], h["art"]) for h in herkunft] == [(ton, "transkript")]
    # die Oberfläche sieht die Gruppe
    namen = await _namen(client, sitzung, unter)
    assert namen["Runde.wav"]["begleiter_anzahl"] == 1
    assert namen["Runde.transkript.json"]["haupt_id"] == ton and namen["Runde.transkript.json"]["rolle"] == "transkript"


async def test_belegter_name_nimmt_den_vollen_namen(umgebung):
    client, sitzung = umgebung
    kopf, _, unter, ton = await _app_mit_ton(client, sitzung)
    await datei(client, sitzung, "Runde.transkript.json", b"fremd", unter)
    r = await _schreiben(client, kopf, ton)
    assert r.status_code == 200 and r.json()["name"] == "Runde.wav.transkript.json"


async def test_begleiter_hat_keine_begleiter(umgebung):
    client, sitzung = umgebung
    kopf, _, _, ton = await _app_mit_ton(client, sitzung)
    b = (await _schreiben(client, kopf, ton)).json()
    assert (await _schreiben(client, kopf, b["id"], rolle="untertitel", zusatz=".srt")).status_code == 422


async def test_ohne_schreibrecht_im_ordner_kein_begleiter(umgebung):
    client, sitzung = umgebung
    kopf, _, _, _ = await _app_mit_ton(client, sitzung)
    apps = (await client.get("/api/v1/ablage/pfad", params={"pfad": "Apps"}, headers=kopf)).json()["id"]
    fremd = await datei(client, sitzung, "Liste.md", b"x", apps)           # in Apps darf die App nur lesen
    assert (await _schreiben(client, kopf, fremd, rolle="sprache", zusatz=".sprache.mp3")).status_code == 403


async def test_anhaengen_holt_die_datei_neben_die_quelle(umgebung):
    client, sitzung = umgebung
    kopf, eigen, unter, ton = await _app_mit_ton(client, sitzung)
    alt = await ordner(client, sitzung, "Transkripte", eigen)
    t = await datei(client, sitzung, "Runde.transkript.json", b"{}", alt)
    r = await client.post(f"/api/v1/ablage/knoten/{ton}/begleiter/transkript", json={"knoten_id": t, "zusatz": ".transkript.json"}, headers=kopf)
    assert r.status_code == 200, r.text
    assert r.json()["parent_id"] == unter and r.json()["name"] == "Runde.transkript.json"
    # die Rolle ist vergeben: eine zweite Datei verdrängt sie nicht
    t2 = await datei(client, sitzung, "Zweit.transkript.json", b"{}", alt)
    r = await client.post(f"/api/v1/ablage/knoten/{ton}/begleiter/transkript", json={"knoten_id": t2, "zusatz": ".transkript.json"}, headers=kopf)
    assert r.status_code == 409


# --- Die Gruppe zieht gemeinsam um ------------------------------------------------------------------------------

async def _gruppe(client, sitzung):
    kopf, eigen, unter, ton = await _app_mit_ton(client, sitzung)
    t = (await _schreiben(client, kopf, ton)).json()["id"]
    s = (await _schreiben(client, kopf, ton, rolle="untertitel", inhalt=b"1", zusatz=".srt")).json()["id"]
    return kopf, eigen, unter, ton, t, s


async def test_umbenennen_der_quelle_benennt_begleiter_mit(umgebung):
    client, sitzung = umgebung
    _, _, unter, ton, _, _ = await _gruppe(client, sitzung)
    r = await client.patch(f"/api/v1/dateien/{ton}/name", json={"name": "Planung.wav"}, headers=sitzung)
    assert r.status_code == 200, r.text
    assert set(await _namen(client, sitzung, unter)) == {"Planung.wav", "Planung.transkript.json", "Planung.srt"}


async def test_umbenennen_mit_belegtem_begleiternamen_aendert_nichts(umgebung):
    client, sitzung = umgebung
    _, _, unter, ton, _, _ = await _gruppe(client, sitzung)
    await datei(client, sitzung, "Planung.transkript.json", b"fremd", unter)
    r = await client.patch(f"/api/v1/dateien/{ton}/name", json={"name": "Planung.wav"}, headers=sitzung)
    assert r.status_code == 409 and "Planung.transkript.json" in r.json()["detail"]
    assert {"Runde.wav", "Runde.transkript.json", "Runde.srt"} <= set(await _namen(client, sitzung, unter))


async def test_verschieben_eines_mitglieds_verschiebt_die_gruppe(umgebung):
    client, sitzung = umgebung
    _, eigen, unter, ton, t, _ = await _gruppe(client, sitzung)
    ziel = await ordner(client, sitzung, "Archiv", eigen)
    r = await client.patch(f"/api/v1/dateien/{t}/ort", json={"parent_id": ziel}, headers=sitzung)  # nur der Begleiter
    assert r.status_code == 200, r.text
    assert set(await _namen(client, sitzung, ziel)) == {"Runde.wav", "Runde.transkript.json", "Runde.srt"}
    assert await _namen(client, sitzung, unter) == {}


async def test_verschieben_mit_belegtem_namen_im_ziel_aendert_nichts(umgebung):
    client, sitzung = umgebung
    _, eigen, unter, ton, _, _ = await _gruppe(client, sitzung)
    ziel = await ordner(client, sitzung, "Archiv", eigen)
    await datei(client, sitzung, "Runde.srt", b"fremd", ziel)
    r = await client.patch(f"/api/v1/dateien/{ton}/ort", json={"parent_id": ziel}, headers=sitzung)
    assert r.status_code == 409 and "Runde.srt" in r.json()["detail"]
    assert len(await _namen(client, sitzung, unter)) == 3


async def test_geloester_begleiter_bleibt_stehen(umgebung):
    client, sitzung = umgebung
    _, eigen, unter, ton, t, _ = await _gruppe(client, sitzung)
    assert (await client.post(f"/api/v1/dateien/{t}/loesen", headers=sitzung)).status_code == 200
    assert (await client.post(f"/api/v1/dateien/{t}/loesen", headers=sitzung)).status_code == 404
    ziel = await ordner(client, sitzung, "Archiv", eigen)
    await client.patch(f"/api/v1/dateien/{ton}/ort", json={"parent_id": ziel}, headers=sitzung)
    assert set(await _namen(client, sitzung, unter)) == {"Runde.transkript.json"}


async def test_webdav_verschiebt_die_gruppe(umgebung):
    client, sitzung = umgebung
    _, eigen, _, _, _, _ = await _gruppe(client, sitzung)
    await ordner(client, sitzung, "Archiv", eigen)
    r = await client.request("MOVE", "/webdav/Apps/Transkription/Besprechungen/Runde.wav", auth=AUTH,
                             headers={"Destination": "/webdav/Apps/Transkription/Archiv/Planung.wav"})
    assert r.status_code == 201, r.text
    ziel_id = (await client.get("/api/v1/dateien/aufloesen", params={"pfad": "Apps/Transkription/Archiv"},
                                headers=sitzung)).json()["id"]
    assert set(await _namen(client, sitzung, ziel_id)) == {"Planung.wav", "Planung.transkript.json", "Planung.srt"}


# --- Papierkorb -------------------------------------------------------------------------------------------------

async def _papierkorb(client, sitzung) -> list[str]:
    return [k["name"] for k in (await client.get("/api/v1/dateien/papierkorb", headers=sitzung)).json()]


async def test_papierkorb_nimmt_die_gruppe_und_bringt_sie_zurueck(umgebung):
    client, sitzung = umgebung
    _, _, unter, ton, _, _ = await _gruppe(client, sitzung)
    assert (await client.delete(f"/api/v1/dateien/{ton}", headers=sitzung)).status_code == 204
    assert await _namen(client, sitzung, unter) == {}
    assert await _papierkorb(client, sitzung) == ["Runde.wav"]                 # eine Zeile für die Gruppe
    await datei(client, sitzung, "Runde.srt", b"neu", unter)                   # inzwischen belegt
    r = await client.post(f"/api/v1/dateien/{ton}/wiederherstellen", headers=sitzung)
    assert r.status_code == 200, r.text
    namen = await _namen(client, sitzung, unter)
    assert {"Runde.wav", "Runde.transkript.json", "Runde.srt", "Runde (wiederhergestellt).srt"} == set(namen)
    assert namen["Runde (wiederhergestellt).srt"]["haupt_id"] == ton


async def test_begleiter_allein_in_den_papierkorb_und_zurueck_zur_quelle(umgebung):
    client, sitzung = umgebung
    _, eigen, unter, ton, t, _ = await _gruppe(client, sitzung)
    await client.delete(f"/api/v1/dateien/{t}", headers=sitzung)
    assert set(await _namen(client, sitzung, unter)) == {"Runde.wav", "Runde.srt"}
    ziel = await ordner(client, sitzung, "Archiv", eigen)
    await client.patch(f"/api/v1/dateien/{ton}/ort", json={"parent_id": ziel}, headers=sitzung)
    r = await client.post(f"/api/v1/dateien/{t}/wiederherstellen", headers=sitzung)
    assert r.status_code == 200 and r.json()["parent_id"] == ziel             # zurück neben die Quelle, nicht ins Alte
    assert set(await _namen(client, sitzung, ziel)) == {"Runde.wav", "Runde.transkript.json", "Runde.srt"}


async def test_neuer_begleiter_ersetzt_einen_im_papierkorb(umgebung):
    client, sitzung = umgebung
    kopf, _, unter, ton, t, _ = await _gruppe(client, sitzung)
    await client.delete(f"/api/v1/dateien/{t}", headers=sitzung)
    r = await _schreiben(client, kopf, ton, inhalt=b'{"neu":1}')
    assert r.status_code == 200 and r.json()["id"] != t and r.json()["name"] == "Runde.transkript.json"
    r = await client.post(f"/api/v1/dateien/{t}/wiederherstellen", headers=sitzung)   # der alte ist jetzt eine Datei
    assert r.status_code == 200
    alt = next(k for k in (await _namen(client, sitzung, unter)).values() if k["id"] == t)
    assert alt["haupt_id"] is None and alt["name"] != "Runde.transkript.json"


async def test_endgueltig_loeschen_nimmt_die_begleiter_mit(umgebung, pool):
    client, sitzung = umgebung
    _, _, _, ton, t, s = await _gruppe(client, sitzung)
    await client.delete(f"/api/v1/dateien/{ton}", headers=sitzung)
    assert (await client.delete(f"/api/v1/dateien/{ton}/endgueltig", headers=sitzung)).status_code == 204
    async with pool.connection() as conn:
        cur = await conn.execute("SELECT count(*) FROM knoten WHERE id = ANY(%s)", ([ton, t, s],))
        assert (await cur.fetchone())[0] == 0


async def test_papierkorb_leeren_nimmt_die_begleiter_mit(umgebung, pool):
    client, sitzung = umgebung
    _, _, _, ton, t, s = await _gruppe(client, sitzung)
    await client.delete(f"/api/v1/dateien/{ton}", headers=sitzung)
    assert (await client.delete("/api/v1/dateien/papierkorb", headers=sitzung)).status_code == 204
    async with pool.connection() as conn:
        cur = await conn.execute("SELECT count(*) FROM knoten WHERE id = ANY(%s)", ([ton, t, s],))
        assert (await cur.fetchone())[0] == 0


async def test_app_verschiebt_eine_gruppe_in_ihrem_zweig(umgebung):
    client, sitzung = umgebung
    kopf, eigen, unter, ton, t, s = await _gruppe(client, sitzung)
    ziel = (await client.post("/api/v1/ablage/ordner", json={"pfad": "Apps/Transkription/Archiv"}, headers=kopf)).json()["id"]
    r = await client.post(f"/api/v1/ablage/knoten/{t}/ort", json={"ordner_id": ziel}, headers=kopf)
    assert r.status_code == 200, r.text
    assert set(await _namen(client, sitzung, ziel)) == {"Runde.wav", "Runde.transkript.json", "Runde.srt"}
    r = await client.post(f"/api/v1/ablage/knoten/{ton}/ort", json={"ordner_id": unter, "name": "Planung.wav"}, headers=kopf)
    assert r.status_code == 200 and r.json()["name"] == "Planung.wav"
    assert set(await _namen(client, sitzung, unter)) == {"Planung.wav", "Planung.transkript.json", "Planung.srt"}
    # aus dem eigenen Zweig heraus nicht (dort darf die App nur lesen)
    apps = (await client.get("/api/v1/ablage/pfad", params={"pfad": "Apps"}, headers=kopf)).json()["id"]
    assert (await client.post(f"/api/v1/ablage/knoten/{ton}/ort", json={"ordner_id": apps}, headers=kopf)).status_code == 403
    # den freigegebenen Ordner selbst nicht
    assert (await client.post(f"/api/v1/ablage/knoten/{eigen}/ort", json={"ordner_id": unter}, headers=kopf)).status_code == 403

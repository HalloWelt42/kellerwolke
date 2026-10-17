"""Ablage für Apps: App-Zugänge (Schlüssel, Rechte je Ordner) und die Ablage-Schnittstelle als Rechte-Matrix.

Ein Konto stellt Schlüssel für seine Apps aus; jede App sieht nur, was ihr Recht abdeckt. Gemeinsame Arbeitsordner
lassen mehrere Apps schreiben. Rechte hängen an Knoten-Kennungen und überstehen Umbenennen.
"""

import httpx
import pytest

from app.main import app_bauen
from module.ablage.dienst import AblageDienst
from module.appzugang.dienst import AppZugangDienst
from module.auth.dienst import AuthDienst
from module.speicher.dienst import SpeicherDienst
from module.suche.dienst import SuchDienst
from module.vorgaenge.dienst import VorgangRegistry
from tests.hilfen import markierter_blobstore


@pytest.fixture
async def umgebung(pool, tmp_path):
    app = app_bauen()
    app.state.pool = pool
    app.state.auth = AuthDienst(pool)
    app.state.speicher = SpeicherDienst(pool, markierter_blobstore(tmp_path))
    app.state.suche = SuchDienst(pool)
    app.state.vorgaenge = VorgangRegistry()
    app.state.appzugang = AppZugangDienst(pool, app.state.speicher)
    app.state.ablage = AblageDienst(pool, app.state.speicher, app.state.appzugang)
    await app.state.auth.benutzer_anlegen("chef", "geheim", rolle="admin")
    await app.state.auth.benutzer_anlegen("gast", "geheim")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/api/v1/auth/login", json={"kennung": "chef", "passwort": "geheim"})
        yield client, {"X-Kellerwolke-Sitzung": r.json()["token"]}


def app_kopf(schluessel: str) -> dict:
    return {"Authorization": f"Bearer {schluessel}"}


async def zugang(client, sitzung, app: str) -> tuple[dict, dict]:
    r = await client.post("/api/v1/app-zugaenge", json={"app": app}, headers=sitzung)
    assert r.status_code == 200, r.text
    return r.json()["zugang"], app_kopf(r.json()["schluessel"])


async def ordner(client, sitzung, name, parent_id=None) -> str:
    r = await client.post("/api/v1/dateien/ordner", json={"name": name, "parent_id": parent_id}, headers=sitzung)
    assert r.status_code == 200, r.text
    return r.json()["id"]


async def datei(client, sitzung, name, daten: bytes, parent_id) -> str:
    r = await client.post("/api/v1/dateien/upload", files={"datei": (name, daten, "application/octet-stream")},
                          data={"parent_id": parent_id}, headers=sitzung)
    assert r.status_code == 200, r.text
    return r.json()["id"]


async def test_zugang_anlegen_mit_vorgaberechten(umgebung):
    client, sitzung = umgebung
    z, kopf = await zugang(client, sitzung, "Transkription")
    assert kopf["Authorization"].startswith("Bearer kw_app_")
    assert {(r["pfad"], r["recht"]) for r in z["rechte"]} == {("Apps", "lesen"), ("Apps/Transkription", "schreiben")}
    ich = (await client.get("/api/v1/ablage/ich", headers=kopf)).json()
    assert ich["app"] == "Transkription" and ich["konto"] == "chef"
    assert (await client.post("/api/v1/app-zugaenge", json={"app": "transkription"}, headers=sitzung)).status_code == 409
    assert (await client.post("/api/v1/app-zugaenge", json={"app": "a/b"}, headers=sitzung)).status_code == 422
    assert "schluessel" not in str((await client.get("/api/v1/app-zugaenge", headers=sitzung)).json())


async def test_ohne_gueltigen_schluessel_nichts(umgebung):
    client, sitzung = umgebung
    assert (await client.get("/api/v1/ablage/ich")).status_code == 401
    assert (await client.get("/api/v1/ablage/ich", headers=sitzung)).status_code == 401          # Sitzung zählt hier nicht
    assert (await client.get("/api/v1/ablage/ich", headers=app_kopf("kw_app_falsch"))).status_code == 401


async def test_rechte_matrix(umgebung):
    client, sitzung = umgebung
    privat = await ordner(client, sitzung, "Privat")
    geheim = await datei(client, sitzung, "geheim.txt", b"nur fuer mich", privat)
    _, t = await zugang(client, sitzung, "Transkription")
    _, s = await zugang(client, sitzung, "Stimmenausgabe")

    # Nutzerdateien außerhalb der Rechte gibt es für die App nicht
    for weg in (f"/api/v1/ablage/knoten/{privat}", f"/api/v1/ablage/knoten/{geheim}/inhalt", "/api/v1/ablage/pfad?pfad=Privat"):
        assert (await client.get(weg, headers=t)).status_code == 404, weg
    # eigener Zweig: anlegen wie mkdir -p, mit Schreibrecht
    r = await client.post("/api/v1/ablage/ordner", json={"pfad": "Apps/Transkription/Läufe/2026"}, headers=t)
    assert r.status_code == 200 and r.json()["pfad"] == "Apps/Transkription/Läufe/2026" and r.json()["recht"] == "schreiben"
    # fremder App-Zweig: lesen ja, schreiben nein
    r = await client.get("/api/v1/ablage/pfad", params={"pfad": "Apps/Stimmenausgabe"}, headers=t)
    assert r.status_code == 200 and r.json()["recht"] == "lesen"
    assert (await client.post("/api/v1/ablage/ordner", json={"pfad": "Apps/Stimmenausgabe/x"}, headers=t)).status_code == 403
    # oberste Ebene und Ordner außerhalb der Rechte: weder sehen noch anlegen
    assert (await client.post("/api/v1/ablage/ordner", json={"pfad": "Neu"}, headers=t)).status_code == 404
    assert (await client.post("/api/v1/ablage/ordner", json={"pfad": "Privat/x"}, headers=t)).status_code == 404
    # Stimmenausgabe sieht Transkription nur lesend
    r = await client.get("/api/v1/ablage/pfad", params={"pfad": "Apps/Transkription/Läufe"}, headers=s)
    assert r.status_code == 200 and r.json()["recht"] == "lesen"


async def test_gemeinsamer_arbeitsordner(umgebung):
    """Manche Apps bearbeiten Dateien zusammen: ein Ordner, den der Nutzer mehreren Apps zum Schreiben freigibt."""
    client, sitzung = umgebung
    zt, t = await zugang(client, sitzung, "Transkription")
    zv, v = await zugang(client, sitzung, "Vertonung")
    apps = (await client.get("/api/v1/ablage/pfad", params={"pfad": "Apps"}, headers=t)).json()["id"]
    gemeinsam = await ordner(client, sitzung, "Gemeinsam", apps)
    for z in (zt, zv):
        rechte = [{"knoten_id": r["knoten_id"], "recht": r["recht"]} for r in z["rechte"]] + [{"knoten_id": gemeinsam, "recht": "schreiben"}]
        r = await client.put(f"/api/v1/app-zugaenge/{z['id']}/rechte", json={"rechte": rechte}, headers=sitzung)
        assert r.status_code == 200, r.text
    for kopf, name in ((t, "Abschrift"), (v, "Ton")):
        r = await client.post("/api/v1/ablage/ordner", json={"pfad": f"Apps/Gemeinsam/Video 1/{name}"}, headers=kopf)
        assert r.status_code == 200 and r.json()["recht"] == "schreiben", r.text
    kinder = (await client.get(f"/api/v1/ablage/knoten/{gemeinsam}/kinder", headers=v)).json()
    assert [k["name"] for k in kinder] == ["Video 1"]


async def test_kinder_seitenweise_und_vererbte_rechte(umgebung):
    client, sitzung = umgebung
    z, t = await zugang(client, sitzung, "Transkription")
    eigen = next(r["knoten_id"] for r in z["rechte"] if r["recht"] == "schreiben")
    for name in ("e", "a", "d", "c", "b"):
        await ordner(client, sitzung, name, eigen)
    await datei(client, sitzung, "0.txt", b"x", eigen)
    seite = (await client.get(f"/api/v1/ablage/knoten/{eigen}/kinder", params={"ab": 2, "anzahl": 2}, headers=t)).json()
    assert [k["name"] for k in seite] == ["c", "d"]                       # Ordner vor Dateien, nach Name
    alle = (await client.get(f"/api/v1/ablage/knoten/{eigen}/kinder", headers=t)).json()
    assert [k["name"] for k in alle][-1] == "0.txt" and all(k["recht"] == "schreiben" for k in alle)
    assert alle[0]["pfad"] == "Apps/Transkription/a"


async def test_inhalt_mit_bereich(umgebung):
    client, sitzung = umgebung
    z, t = await zugang(client, sitzung, "Transkription")
    eigen = next(r["knoten_id"] for r in z["rechte"] if r["recht"] == "schreiben")
    d = await datei(client, sitzung, "ton.wav", bytes(range(256)) * 4, eigen)
    r = await client.get(f"/api/v1/ablage/knoten/{d}/inhalt", headers=t)
    assert r.status_code == 200 and r.content == bytes(range(256)) * 4 and r.headers["etag"]
    r = await client.get(f"/api/v1/ablage/knoten/{d}/inhalt", headers={**t, "Range": "bytes=10-19"})
    assert r.status_code == 206 and r.content == bytes(range(10, 20)) and r.headers["content-range"] == "bytes 10-19/1024"
    k = (await client.get(f"/api/v1/ablage/knoten/{d}", headers=t)).json()
    assert k["groesse"] == 1024 and k["pfad"] == "Apps/Transkription/ton.wav" and k["typ"] == "datei"


async def test_rechte_ueberstehen_umbenennen_und_loeschen_sperrt(umgebung):
    client, sitzung = umgebung
    z, t = await zugang(client, sitzung, "Transkription")
    eigen = next(r["knoten_id"] for r in z["rechte"] if r["recht"] == "schreiben")
    unter = await ordner(client, sitzung, "Läufe", eigen)
    assert (await client.patch(f"/api/v1/dateien/{eigen}/name", json={"name": "Abschrift"}, headers=sitzung)).status_code == 200
    r = await client.get(f"/api/v1/ablage/knoten/{unter}", headers=t)
    assert r.status_code == 200 and r.json()["pfad"] == "Apps/Abschrift/Läufe" and r.json()["recht"] == "schreiben"
    assert (await client.delete(f"/api/v1/dateien/{eigen}", headers=sitzung)).status_code in (200, 204)
    assert (await client.get(f"/api/v1/ablage/knoten/{unter}", headers=t)).status_code == 404     # liegt im Papierkorb


async def test_sperren_erneuern_loeschen(umgebung):
    client, sitzung = umgebung
    z, t = await zugang(client, sitzung, "Transkription")
    assert (await client.patch(f"/api/v1/app-zugaenge/{z['id']}", json={"aktiv": False}, headers=sitzung)).status_code == 200
    assert (await client.get("/api/v1/ablage/ich", headers=t)).status_code == 401
    await client.patch(f"/api/v1/app-zugaenge/{z['id']}", json={"aktiv": True}, headers=sitzung)
    assert (await client.get("/api/v1/ablage/ich", headers=t)).status_code == 200
    r = await client.post(f"/api/v1/app-zugaenge/{z['id']}/erneuern", headers=sitzung)
    neu = app_kopf(r.json()["schluessel"])
    assert (await client.get("/api/v1/ablage/ich", headers=t)).status_code == 401              # alter Schlüssel tot
    assert (await client.get("/api/v1/ablage/ich", headers=neu)).status_code == 200
    assert (await client.delete(f"/api/v1/app-zugaenge/{z['id']}", headers=sitzung)).status_code == 204
    assert (await client.get("/api/v1/ablage/ich", headers=neu)).status_code == 401
    assert (await client.get("/api/v1/ablage/pfad", params={"pfad": "Apps/Transkription"}, headers=sitzung)).status_code == 401


async def test_rechte_nur_auf_eigene_ordner(umgebung):
    client, sitzung = umgebung
    z, _ = await zugang(client, sitzung, "Transkription")
    privat = await ordner(client, sitzung, "Privat")
    d = await datei(client, sitzung, "x.txt", b"x", privat)
    r = await client.put(f"/api/v1/app-zugaenge/{z['id']}/rechte", json={"rechte": [{"knoten_id": d, "recht": "lesen"}]}, headers=sitzung)
    assert r.status_code == 422                                           # Dateien nicht, nur Ordner
    login = await client.post("/api/v1/auth/login", json={"kennung": "gast", "passwort": "geheim"})
    gast = {"X-Kellerwolke-Sitzung": login.json()["token"]}
    r = await client.put(f"/api/v1/app-zugaenge/{z['id']}/rechte", json={"rechte": []}, headers=gast)
    assert r.status_code == 404                                           # fremder Zugang
    gast_ordner = await ordner(client, gast, "Gast")
    r = await client.put(f"/api/v1/app-zugaenge/{z['id']}/rechte", json={"rechte": [{"knoten_id": gast_ordner, "recht": "lesen"}]}, headers=sitzung)
    assert r.status_code == 422                                           # fremder Ordner


# --- K3: Hochladen als Strom, Überschreiben nur mit dem gelesenen Stand -------------------------------------------

async def test_datei_schreiben_und_ueberschreiben_nur_mit_stand(umgebung):
    client, sitzung = umgebung
    _, t = await zugang(client, sitzung, "Transkription")
    weg = "/api/v1/ablage/datei"
    r = await client.put(weg, params={"pfad": "Apps/Transkription/a.json"}, content=b'{"v": 1}', headers=t)
    assert r.status_code == 200, r.text
    erst = r.json()
    assert erst["pfad"] == "Apps/Transkription/a.json" and erst["groesse"] == 8 and erst["etag"]
    # ohne Stand: kein stilles Überschreiben
    assert (await client.put(weg, params={"pfad": "Apps/Transkription/a.json"}, content=b"x", headers=t)).status_code == 428
    # veralteter Stand: abgewiesen
    r = await client.put(weg, params={"pfad": "Apps/Transkription/a.json"}, content=b"x", headers={**t, "If-Match": "veraltet"})
    assert r.status_code == 412
    # gelesener Stand: neue Version, neuer ETag
    r = await client.put(weg, params={"pfad": "Apps/Transkription/a.json"}, content=b'{"v": 2}', headers={**t, "If-Match": erst["etag"]})
    assert r.status_code == 200 and r.json()["etag"] != erst["etag"]
    assert (await client.get(f"/api/v1/ablage/knoten/{erst['id']}/inhalt", headers=t)).content == b'{"v": 2}'
    versionen = (await client.get(f"/api/v1/dateien/{erst['id']}/versionen", headers=sitzung)).json()
    assert len(versionen) == 2
    # nur neu anlegen
    assert (await client.put(weg, params={"pfad": "Apps/Transkription/a.json"}, content=b"x", headers={**t, "If-None-Match": "*"})).status_code == 412
    assert (await client.put(weg, params={"pfad": "Apps/Transkription/b.json"}, content=b"x", headers={**t, "If-None-Match": "*"})).status_code == 200
    # per Kennung: nur mit If-Match
    neu = (await client.get(f"/api/v1/ablage/knoten/{erst['id']}", headers=t)).json()
    assert (await client.put(f"/api/v1/ablage/knoten/{erst['id']}/inhalt", content=b"y", headers=t)).status_code == 428
    r = await client.put(f"/api/v1/ablage/knoten/{erst['id']}/inhalt", content=b"y", headers={**t, "If-Match": neu["etag"]})
    assert r.status_code == 200 and r.json()["id"] == erst["id"]


async def test_gleichzeitig_mit_demselben_stand_gewinnt_genau_einer(umgebung):
    """Zwei Apps bearbeiten dieselbe Datei im gemeinsamen Ordner und schreiben gleichzeitig mit demselben Stand."""
    import asyncio
    client, sitzung = umgebung
    _, t = await zugang(client, sitzung, "Transkription")
    erst = (await client.put("/api/v1/ablage/datei", params={"pfad": "Apps/Transkription/geteilt.txt"}, content=b"0", headers=t)).json()

    async def schreiben(inhalt: bytes):
        return await client.put("/api/v1/ablage/datei", params={"pfad": "Apps/Transkription/geteilt.txt"}, content=inhalt,
                                headers={**t, "If-Match": erst["etag"]})

    ergebnisse = await asyncio.gather(*(schreiben(f"stand {i}".encode()) for i in range(5)))
    assert sorted(r.status_code for r in ergebnisse) == [200, 412, 412, 412, 412]
    gewinner = next(r for r in ergebnisse if r.status_code == 200).json()
    inhalt = (await client.get(f"/api/v1/ablage/knoten/{gewinner['id']}/inhalt", headers=t)).content
    assert inhalt.startswith(b"stand ")


async def test_schreiben_nur_wo_erlaubt(umgebung):
    client, sitzung = umgebung
    await ordner(client, sitzung, "Privat")
    _, t = await zugang(client, sitzung, "Transkription")
    await zugang(client, sitzung, "Stimmenausgabe")
    weg = "/api/v1/ablage/datei"
    assert (await client.put(weg, params={"pfad": "Apps/Stimmenausgabe/x.txt"}, content=b"x", headers=t)).status_code == 403
    assert (await client.put(weg, params={"pfad": "Privat/x.txt"}, content=b"x", headers=t)).status_code == 404
    assert (await client.put(weg, params={"pfad": "x.txt"}, content=b"x", headers=t)).status_code == 404
    assert (await client.put(weg, params={"pfad": "Apps/Transkription/fehlt/x.txt"}, content=b"x", headers=t)).status_code == 404
    await client.post("/api/v1/ablage/ordner", json={"pfad": "Apps/Transkription/ordner"}, headers=t)
    assert (await client.put(weg, params={"pfad": "Apps/Transkription/ordner"}, content=b"x", headers=t)).status_code == 409


async def test_grosser_strom_und_grenze(umgebung, tmp_path, monkeypatch):
    """Ein Körper in vielen Stücken kommt vollständig an; über der Grenze bleibt nichts zurück."""
    from app.config import EINSTELLUNGEN
    client, sitzung = umgebung
    _, t = await zugang(client, sitzung, "Transkription")
    stueck = bytes(range(256)) * 4096                                    # 1 MiB

    async def koerper(anzahl):
        for _ in range(anzahl):
            yield stueck

    r = await client.put("/api/v1/ablage/datei", params={"pfad": "Apps/Transkription/gross.bin"}, content=koerper(6), headers=t)
    assert r.status_code == 200 and r.json()["groesse"] == 6 * len(stueck), r.text
    inhalt = (await client.get(f"/api/v1/ablage/knoten/{r.json()['id']}/inhalt", headers=t)).content
    assert inhalt == stueck * 6
    vorher = sorted(p.name for p in tmp_path.rglob("*") if p.is_file())
    import dataclasses
    import module.ablage.api as ablage_api
    monkeypatch.setattr(ablage_api, "EINSTELLUNGEN", dataclasses.replace(EINSTELLUNGEN, max_upload=2 * len(stueck)))
    r = await client.put("/api/v1/ablage/datei", params={"pfad": "Apps/Transkription/zu-gross.bin"}, content=koerper(4), headers=t)
    assert r.status_code == 413
    assert sorted(p.name for p in tmp_path.rglob("*") if p.is_file()) == vorher                # keine Reste im Pool
    assert (await client.get("/api/v1/ablage/pfad", params={"pfad": "Apps/Transkription/zu-gross.bin"}, headers=t)).status_code == 404


# --- K4: Metadaten (Inhaltstyp, App, Felder) und Herkunft --------------------------------------------------------

async def test_inhaltstyp_app_und_felder(umgebung):
    client, sitzung = umgebung
    _, t = await zugang(client, sitzung, "Transkription")
    r = await client.put("/api/v1/ablage/datei", params={"pfad": "Apps/Transkription/a.vtt"}, content=b"WEBVTT", headers=t)
    k = r.json()
    assert k["inhaltstyp"] == "text/vtt" and k["app"] == "Transkription" and k["felder"] == {}       # aus dem Namen
    r = await client.put("/api/v1/ablage/datei", params={"pfad": "Apps/Transkription/roh"}, content=b"{}",
                         headers={**t, "Content-Type": "application/json; charset=utf-8"})
    assert r.json()["inhaltstyp"] == "application/json"                                                # vom Schreiber
    inhalt = await client.get(f"/api/v1/ablage/knoten/{k['id']}/inhalt", headers=t)
    assert inhalt.headers["content-type"].startswith("text/vtt")
    browser = await client.get(f"/api/v1/dateien/{k['id']}/inhalt", headers=sitzung)
    assert browser.headers["content-type"].startswith("text/vtt")                                     # auch im Browser
    r = await client.patch(f"/api/v1/ablage/knoten/{k['id']}/felder", json={"felder": {"sprache": "de", "dauer_s": 52.4}}, headers=t)
    assert r.status_code == 200 and r.json()["felder"] == {"sprache": "de", "dauer_s": 52.4}
    r = await client.patch(f"/api/v1/ablage/knoten/{k['id']}/felder", json={"felder": {"dauer_s": None, "modell": "w"}}, headers=t)
    assert r.json()["felder"] == {"sprache": "de", "modell": "w"}                                      # null entfernt
    kinder = (await client.get(f"/api/v1/ablage/knoten/{k['parent_id']}/kinder", headers=t)).json()
    assert next(x for x in kinder if x["id"] == k["id"])["felder"]["sprache"] == "de"
    # zu groß
    r = await client.patch(f"/api/v1/ablage/knoten/{k['id']}/felder", json={"felder": {"x": "a" * 70000}}, headers=t)
    assert r.status_code == 422


async def test_felder_nur_mit_schreibrecht_und_suche_nur_im_sichtbaren(umgebung, pool):
    client, sitzung = umgebung
    privat = await ordner(client, sitzung, "Privat")
    _, t = await zugang(client, sitzung, "Transkription")
    _, s = await zugang(client, sitzung, "Stimmenausgabe")
    a = (await client.put("/api/v1/ablage/datei", params={"pfad": "Apps/Transkription/a.json"}, content=b"{}", headers=t)).json()
    await client.patch(f"/api/v1/ablage/knoten/{a['id']}/felder", json={"felder": {"sprache": "de"}}, headers=t)
    assert (await client.patch(f"/api/v1/ablage/knoten/{a['id']}/felder", json={"felder": {"x": 1}}, headers=s)).status_code == 403
    # eine Datei mit passendem Feld, die keine App sehen darf
    geheim = await datei(client, sitzung, "geheim.json", b"{}", privat)
    from module.ablage import metadaten
    async with pool.connection() as conn:                                                              # Feld direkt setzen
        await metadaten.felder_mischen(conn, geheim, {"sprache": "de"}, "Konto")
    treffer = (await client.post("/api/v1/ablage/suche", json={"felder": {"sprache": "de"}}, headers=s)).json()
    assert [x["id"] for x in treffer] == [a["id"]]
    assert (await client.post("/api/v1/ablage/suche", json={"felder": {"sprache": "en"}}, headers=s)).json() == []


async def test_herkunft_ueberlebt_umbenennen_und_bleibt_privat(umgebung):
    client, sitzung = umgebung
    _, t = await zugang(client, sitzung, "Transkription")
    _, v = await zugang(client, sitzung, "Vertonung")
    ton = (await client.put("/api/v1/ablage/datei", params={"pfad": "Apps/Vertonung/video.wav"}, content=b"RIFF", headers=v)).json()
    text = (await client.put("/api/v1/ablage/datei", params={"pfad": "Apps/Transkription/video.json"}, content=b"{}", headers=t)).json()
    r = await client.post(f"/api/v1/ablage/knoten/{text['id']}/herkunft", json={"von_id": ton["id"], "art": "transkript_zu"}, headers=t)
    assert r.status_code == 200 and r.json()[0]["art"] == "transkript_zu" and r.json()[0]["app"] == "Transkription"
    # Vertonung sieht den Bezug von ihrer Seite aus (sie darf Apps lesen)
    bezuege = (await client.get(f"/api/v1/ablage/knoten/{ton['id']}/herkunft", headers=v)).json()
    assert [(b["von_id"], b["zu_id"]) for b in bezuege] == [(ton["id"], text["id"])]
    # Umbenennen ändert nichts am Bezug
    await client.patch(f"/api/v1/dateien/{ton['id']}/name", json={"name": "neu.wav"}, headers=sitzung)
    assert len((await client.get(f"/api/v1/ablage/knoten/{text['id']}/herkunft", headers=t)).json()) == 1
    # Rechte: Bezug nur mit Schreibrecht auf die neue Datei, Art nur in der erlaubten Form, nicht auf sich selbst
    assert (await client.post(f"/api/v1/ablage/knoten/{ton['id']}/herkunft", json={"von_id": text["id"], "art": "x"}, headers=t)).status_code == 403
    assert (await client.post(f"/api/v1/ablage/knoten/{text['id']}/herkunft", json={"von_id": ton["id"], "art": "Transkript"}, headers=t)).status_code == 422
    assert (await client.post(f"/api/v1/ablage/knoten/{text['id']}/herkunft", json={"von_id": text["id"], "art": "x"}, headers=t)).status_code == 422
    # entfernen
    r = await client.delete(f"/api/v1/ablage/knoten/{text['id']}/herkunft", params={"von_id": ton["id"], "art": "transkript_zu"}, headers=t)
    assert r.status_code == 204 and (await client.get(f"/api/v1/ablage/knoten/{text['id']}/herkunft", headers=t)).json() == []

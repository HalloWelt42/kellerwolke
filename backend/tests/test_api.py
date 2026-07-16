"""API-Tests (httpx gegen die ASGI-App): Login, Datei-Lebenszyklus, Suche,
Fremdzugriff-Schutz (Isolation) und Admin-Guard."""

import asyncio

import httpx
import pytest

from app.main import app_bauen
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
    # Indizierung laeuft jetzt als Hintergrund-Vorgang -> kurz auf das Ergebnis warten.
    treffer = []
    for _ in range(50):
        r = await client.get("/api/v1/suche", params={"q": "Rechnung"}, headers=h)
        assert r.status_code == 200
        treffer = r.json()
        if any(k["name"] == "brief.txt" for k in treffer):
            break
        await asyncio.sleep(0.02)
    assert any(k["name"] == "brief.txt" for k in treffer)


async def test_vorgaenge_route(umgebung):
    client, _ = umgebung
    h = await _anmelden(client)
    await _upload(client, h, "doku.txt", b"Inhalt zum Indizieren")
    # Der Upload erzeugt einen Indizierungs-Vorgang; er taucht in der Liste auf
    # und ist nach kurzer Zeit fertig.
    status = None
    for _ in range(50):
        r = await client.get("/api/v1/vorgaenge", headers=h)
        assert r.status_code == 200
        liste = r.json()
        if liste:
            status = liste[0]["status"]
            assert liste[0]["art"] == "indizierung"
            if status == "fertig":
                break
        await asyncio.sleep(0.02)
    assert status == "fertig"
    # Aufraeumen entfernt abgeschlossene Vorgaenge.
    r = await client.post("/api/v1/vorgaenge/aufraeumen", headers=h)
    assert r.status_code == 204
    r = await client.get("/api/v1/vorgaenge", headers=h)
    assert r.json() == []


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


async def _ordner(client, headers, name, parent=None):
    nutzlast: dict = {"name": name}
    if parent:
        nutzlast["parent_id"] = parent
    return (await client.post("/api/v1/dateien/ordner", json=nutzlast, headers=headers)).json()


async def test_verschieben_in_sich_selbst_409(umgebung):
    client, _ = umgebung
    h = await _anmelden(client)
    o = await _ordner(client, h, "O")
    r = await client.patch(f"/api/v1/dateien/{o['id']}/ort", json={"parent_id": o["id"]}, headers=h)
    assert r.status_code == 409


async def test_verschieben_in_nachkomme_409(umgebung):
    client, _ = umgebung
    h = await _anmelden(client)
    a = await _ordner(client, h, "A")
    b = await _ordner(client, h, "B", a["id"])
    r = await client.patch(f"/api/v1/dateien/{a['id']}/ort", json={"parent_id": b["id"]}, headers=h)
    assert r.status_code == 409


async def test_upload_zu_gross_413(umgebung, monkeypatch):
    from types import SimpleNamespace

    monkeypatch.setattr("module.speicher.api.EINSTELLUNGEN", SimpleNamespace(max_upload=10))
    client, _ = umgebung
    h = await _anmelden(client)
    r = await _upload(client, h, "gross.bin", b"x" * 100)
    assert r.status_code == 413


async def test_leerer_name_422(umgebung):
    client, _ = umgebung
    h = await _anmelden(client)
    r = await client.post("/api/v1/dateien/ordner", json={"name": "   "}, headers=h)
    assert r.status_code == 422


async def test_ungueltige_rolle_422(umgebung):
    client, _ = umgebung
    h = await _anmelden(client)
    r = await client.post(
        "/api/v1/admin/benutzer", json={"name": "x", "passwort": "pw", "rolle": "root"}, headers=h
    )
    assert r.status_code == 422


async def test_letzter_admin_geschuetzt(umgebung):
    client, _ = umgebung
    h = await _anmelden(client)
    liste = (await client.get("/api/v1/admin/benutzer", headers=h)).json()
    chef = next(b for b in liste if b["name"] == "chef")
    r = await client.patch(
        f"/api/v1/admin/benutzer/{chef['id']}", json={"aktiv": False}, headers=h
    )
    assert r.status_code == 409


async def test_admin_sperrt_sich_nicht_selbst(umgebung):
    client, _ = umgebung
    h = await _anmelden(client)  # chef ist Admin
    chef = next(b for b in (await client.get("/api/v1/admin/benutzer", headers=h)).json()
                if b["name"] == "chef")
    # Zweiten Admin anlegen, damit es NICHT um den letzten Admin geht.
    await client.post("/api/v1/admin/benutzer",
                      json={"name": "co", "passwort": "pw", "rolle": "admin"}, headers=h)
    # Trotzdem: chef darf sich selbst weder deaktivieren noch herabstufen.
    r = await client.patch(f"/api/v1/admin/benutzer/{chef['id']}", json={"aktiv": False}, headers=h)
    assert r.status_code == 409
    r = await client.patch(f"/api/v1/admin/benutzer/{chef['id']}", json={"rolle": "mitglied"}, headers=h)
    assert r.status_code == 409
    # Den anderen Admin darf chef hingegen deaktivieren.
    co = next(b for b in (await client.get("/api/v1/admin/benutzer", headers=h)).json()
              if b["name"] == "co")
    r = await client.patch(f"/api/v1/admin/benutzer/{co['id']}", json={"aktiv": False}, headers=h)
    assert r.status_code == 204


async def test_externe_quelle_einhaengen_und_lesen(umgebung, tmp_path):
    client, _ = umgebung
    h = await _anmelden(client)
    quelle = tmp_path / "platte"
    (quelle / "unterordner").mkdir(parents=True)
    (quelle / "datei.txt").write_bytes(b"externer Inhalt")
    (quelle / "unterordner" / "tief.txt").write_bytes(b"tief")

    liste = (await client.get("/api/v1/admin/benutzer", headers=h)).json()
    chef = next(b for b in liste if b["name"] == "chef")
    r = await client.post(
        "/api/v1/admin/externe-quelle",
        json={"besitzer_id": chef["id"], "name": "Platte", "pfad": str(quelle)},
        headers=h,
    )
    assert r.status_code == 201, r.text
    extern_id = r.json()["id"]
    assert r.json()["typ"] == "extern"

    eintraege = (await client.get(f"/api/v1/dateien/extern/{extern_id}", headers=h)).json()
    assert {e["name"] for e in eintraege} == {"unterordner", "datei.txt"}

    inhalt = await client.get(
        f"/api/v1/dateien/extern/{extern_id}/inhalt", params={"unterpfad": "datei.txt"}, headers=h
    )
    assert inhalt.content == b"externer Inhalt"

    tief = (await client.get(
        f"/api/v1/dateien/extern/{extern_id}", params={"unterpfad": "unterordner"}, headers=h
    )).json()
    assert any(e["name"] == "tief.txt" for e in tief)

    # Pfad-Ausbruch wird geblockt
    r = await client.get(
        f"/api/v1/dateien/extern/{extern_id}/inhalt",
        params={"unterpfad": "../../etc/passwd"}, headers=h,
    )
    assert r.status_code == 404


async def test_externe_quelle_nur_admin(umgebung, tmp_path):
    client, app = umgebung
    await app.state.auth.benutzer_anlegen("gast", "pw")
    h_gast = await _anmelden(client, "gast", "pw")
    h_chef = await _anmelden(client)
    liste = (await client.get("/api/v1/admin/benutzer", headers=h_chef)).json()
    gast = next(b for b in liste if b["name"] == "gast")
    r = await client.post(
        "/api/v1/admin/externe-quelle",
        json={"besitzer_id": gast["id"], "name": "X", "pfad": str(tmp_path)},
        headers=h_gast,
    )
    assert r.status_code == 403


async def test_sync_journal(umgebung):
    client, _ = umgebung
    h = await _anmelden(client)
    await _upload(client, h, "eins.txt", b"a")
    await _upload(client, h, "zwei.txt", b"b")
    alle = (await client.get("/api/v1/sync/journal", headers=h)).json()
    assert len(alle) == 2
    assert [e["typ"] for e in alle] == ["erstellt", "erstellt"]
    seqs = [e["seq"] for e in alle]
    spaeter = (await client.get(f"/api/v1/sync/journal?seit={seqs[0]}", headers=h)).json()
    assert len(spaeter) == 1
    assert spaeter[0]["seq"] == seqs[1]


async def test_download_mit_range(umgebung):
    """Fortsetzbarer Download: Range muss 206 plus exakten Ausschnitt liefern.

    Regression: frueher las der Download immer die ganze Datei und kannte gar
    keinen Range - ein abgebrochener 1-GB-Download begann wieder bei 0.
    """
    client, _ = umgebung
    h = await _anmelden(client)
    daten = bytes(range(256)) * 40
    r = await _upload(client, h, "teil.bin", daten)
    knoten_id = r.json()["id"]

    ganz = await client.get(f"/api/v1/dateien/{knoten_id}/inhalt", headers=h)
    assert ganz.status_code == 200
    assert ganz.content == daten
    assert ganz.headers.get("accept-ranges") == "bytes"

    teil = await client.get(
        f"/api/v1/dateien/{knoten_id}/inhalt", headers={**h, "Range": "bytes=100-199"}
    )
    assert teil.status_code == 206
    assert teil.content == daten[100:200]
    assert teil.headers["content-range"] == f"bytes 100-199/{len(daten)}"

    # Suffix-Form: die letzten 10 Bytes
    letzte = await client.get(
        f"/api/v1/dateien/{knoten_id}/inhalt", headers={**h, "Range": "bytes=-10"}
    )
    assert letzte.status_code == 206
    assert letzte.content == daten[-10:]


async def test_download_dateiname_mit_umlaut(umgebung):
    """Umlaute im Dateinamen duerfen den Kopf nicht zerlegen.

    Der Name wanderte frueher roh in Content-Disposition - bei "Übergewicht.txt"
    oder einem Anfuehrungszeichen im Namen ging das schief.
    """
    client, _ = umgebung
    h = await _anmelden(client)
    r = await _upload(client, h, "Übergewicht bei Kindern.txt", b"inhalt")
    knoten_id = r.json()["id"]
    antwort = await client.get(f"/api/v1/dateien/{knoten_id}/inhalt", headers=h)
    assert antwort.status_code == 200
    cd = antwort.headers["content-disposition"]
    # RFC-5987-Form traegt den echten Namen, der ASCII-Teil bleibt als Rueckfall.
    assert "filename*=UTF-8''" in cd
    assert "%C3%9C" in cd  # das grosse U-Umlaut, prozentkodiert

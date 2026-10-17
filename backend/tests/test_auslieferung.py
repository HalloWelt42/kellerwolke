"""Auslieferung an einer Stelle: Bereiche nach RFC 9110, Validierung über ETag, gleiche Regeln für eigene und
geteilte Dateien, externe Quellen strömen mit sauberem Dateinamen."""

import pytest

from app.auslieferung import Bereich, NichtErfuellbar, bereich_aus_kopf
from tests.test_api import _anmelden, _upload, umgebung  # noqa: F401 - Fixture


@pytest.mark.parametrize("kopf,erwartet", [
    (None, None),
    ("bytes=0-9", Bereich(0, 9)),
    ("bytes=5-", Bereich(5, 99)),
    ("bytes=-10", Bereich(90, 99)),
    ("bytes=-500", Bereich(0, 99)),
    ("bytes=90-500", Bereich(90, 99)),
    ("bytes=9-3", None),
    ("bytes=0-1,5-6", None),
    ("unsinn", None),
])
def test_bereich_aus_kopf(kopf, erwartet):
    assert bereich_aus_kopf(kopf, 100) == erwartet


@pytest.mark.parametrize("kopf", ["bytes=100-", "bytes=500-600", "bytes=-0"])
def test_bereich_unerfuellbar(kopf):
    with pytest.raises(NichtErfuellbar):
        bereich_aus_kopf(kopf, 100)


async def _datei(client, h, daten=bytes(range(100))):
    return (await _upload(client, h, "zahlen.bin", daten)).json()


async def test_ganz_und_bereich(umgebung):
    client, _ = umgebung
    h = await _anmelden(client)
    k = await _datei(client, h)
    url = f"/api/v1/dateien/{k['id']}/inhalt"
    ganz = await client.get(url, headers=h)
    assert ganz.status_code == 200 and len(ganz.content) == 100
    assert ganz.headers["etag"] == f'"{k["etag"]}"'
    teil = await client.get(url, headers={**h, "Range": "bytes=-10"})
    assert teil.status_code == 206 and teil.content == bytes(range(90, 100))
    assert teil.headers["content-range"] == "bytes 90-99/100"


async def test_unerfuellbar_gibt_416(umgebung):
    client, _ = umgebung
    h = await _anmelden(client)
    k = await _datei(client, h)
    r = await client.get(f"/api/v1/dateien/{k['id']}/inhalt", headers={**h, "Range": "bytes=200-"})
    assert r.status_code == 416 and r.headers["content-range"] == "bytes */100"


async def test_if_range_mit_altem_stand_liefert_ganz(umgebung):
    client, _ = umgebung
    h = await _anmelden(client)
    k = await _datei(client, h)
    url = f"/api/v1/dateien/{k['id']}/inhalt"
    r = await client.get(url, headers={**h, "Range": "bytes=0-9", "If-Range": '"veraltet"'})
    assert r.status_code == 200 and len(r.content) == 100
    r = await client.get(url, headers={**h, "Range": "bytes=0-9", "If-Range": f'"{k["etag"]}"'})
    assert r.status_code == 206 and len(r.content) == 10


async def test_if_none_match_gibt_304(umgebung):
    client, _ = umgebung
    h = await _anmelden(client)
    k = await _datei(client, h)
    r = await client.get(f"/api/v1/dateien/{k['id']}/inhalt", headers={**h, "If-None-Match": f'"{k["etag"]}"'})
    assert r.status_code == 304 and r.content == b""


async def test_geteilt_mit_gleichen_regeln(umgebung):
    client, app = umgebung
    h = await _anmelden(client)
    gast = await app.state.auth.benutzer_anlegen("gast", "geheim2")
    k = await _datei(client, h)
    r = await client.post(f"/api/v1/dateien/{k['id']}/teilen", json={"ziel_benutzer_id": str(gast["id"])}, headers=h)
    assert r.status_code == 204
    hg = await _anmelden(client, "gast", "geheim2")
    teil = await client.get(f"/api/v1/dateien/geteilt/{k['id']}/inhalt", headers={**hg, "Range": "bytes=10-19"})
    assert teil.status_code == 206 and teil.content == bytes(range(10, 20))
    # Der eigene Weg bleibt dem Eigentümer vorbehalten.
    assert (await client.get(f"/api/v1/dateien/{k['id']}/inhalt", headers=hg)).status_code == 404


async def test_extern_stroemt_mit_sonderzeichen_im_namen(umgebung, tmp_path):
    client, _ = umgebung
    h = await _anmelden(client)
    quelle = tmp_path / "platte"
    quelle.mkdir()
    (quelle / "Preis 5 € - Čapek.txt").write_bytes(b"x" * 3000)
    chef = next(b for b in (await client.get("/api/v1/admin/benutzer", headers=h)).json() if b["name"] == "chef")
    k = (await client.post("/api/v1/admin/externe-quelle", json={"besitzer_id": chef["id"], "name": "Platte",
                                                                  "pfad": str(quelle)}, headers=h)).json()
    liste = (await client.get(f"/api/v1/dateien/extern/{k['id']}", headers=h)).json()
    assert liste[0]["geaendert_am"] is not None
    r = await client.get(f"/api/v1/dateien/extern/{k['id']}/inhalt", params={"unterpfad": "Preis 5 € - Čapek.txt"},
                         headers={**h, "Range": "bytes=0-99"})
    assert r.status_code == 206 and len(r.content) == 100
    assert "filename*=UTF-8''Preis%205%20%E2%82%AC" in r.headers["content-disposition"]
    # Schreiben gibt es nicht.
    assert (await client.post(f"/api/v1/dateien/extern/{k['id']}/ordner", json={"name": "x"}, headers=h)).status_code in (404, 405)

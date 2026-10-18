"""Aktionen der Apps und Anfragen: das Recht einer App auf eine Datei außerhalb ihrer Ordner gilt nur, solange eine
Anfrage für genau diese Datei offen ist (Nutzer, 17.10.2026: "Je Auftrag, nur diese Datei")."""

import asyncio
import time

from tests.test_ablage import datei, ordner, umgebung, zugang  # noqa: F401 (Fixture)

AKTIONEN = {
    "adresse": "https://192.168.178.49:8631",
    "aktionen": [
        {"kennung": "transkribieren", "titel": "Transkribieren", "titel_erneut": "Neu transkribieren",
         "symbol": "fa-closed-captioning", "typen": ["audio/*", "video/*"], "rolle": "transkript"},
        {"kennung": "oeffnen", "titel": "In Transkription öffnen", "symbol": "fa-up-right-from-square",
         "typen": ["audio/*", "video/*"], "art": "oeffnen", "rolle": "transkript"},
    ],
}


async def _aufbau(client, sitzung):
    """App Transkription mit gemeldeten Aktionen; im Ordner Besprechungen des Kontos (außerhalb ihrer Rechte) liegen
    ein Ton und ein Text."""
    _, kopf = await zugang(client, sitzung, "Transkription")
    r = await client.put("/api/v1/ablage/aktionen", json=AKTIONEN, headers=kopf)
    assert r.status_code == 200, r.text
    besprechungen = await ordner(client, sitzung, "Besprechungen")
    ton = await datei(client, sitzung, "Runde.wav", b"RIFF-ton", besprechungen)
    text = await datei(client, sitzung, "Notiz.md", b"# Notiz", besprechungen)
    return kopf, besprechungen, ton, text


async def _stellen(client, sitzung, ton, kennung="transkribieren"):
    aktionen = (await client.get(f"/api/v1/dateien/{ton}/aktionen", headers=sitzung)).json()
    a = next(x for x in aktionen if x["kennung"] == kennung)
    r = await client.post("/api/v1/anfragen", json={"zugang_id": a["zugang_id"], "aktion": kennung, "knoten_id": ton},
                          headers=sitzung)
    assert r.status_code == 200, r.text
    return r.json()


def _mit(kopf, anfrage_id):
    return {**kopf, "X-Kellerwolke-Anfrage": anfrage_id}


async def test_aktionen_passen_nach_inhaltstyp(umgebung):
    client, sitzung = umgebung
    _, _, ton, text = await _aufbau(client, sitzung)
    aktionen = (await client.get(f"/api/v1/dateien/{ton}/aktionen", headers=sitzung)).json()
    assert [(a["kennung"], a["titel"], a["erreichbar"], a["erneut"]) for a in aktionen] == [
        ("transkribieren", "Transkribieren", True, False), ("oeffnen", "In Transkription öffnen", True, False)]
    assert (await client.get(f"/api/v1/dateien/{text}/aktionen", headers=sitzung)).json() == []
    zugang_id = aktionen[0]["zugang_id"]
    r = await client.post("/api/v1/anfragen", json={"zugang_id": zugang_id, "aktion": "transkribieren", "knoten_id": text},
                          headers=sitzung)
    assert r.status_code == 422


async def test_recht_gilt_nur_waehrend_der_anfrage(umgebung):
    client, sitzung = umgebung
    kopf, _, ton, text = await _aufbau(client, sitzung)
    assert (await client.get(f"/api/v1/ablage/knoten/{ton}/inhalt", headers=kopf)).status_code == 404   # ohne Anfrage nichts
    anfrage = (await _stellen(client, sitzung, ton))["anfrage"]
    assert anfrage["zustand"] == "wartet" and anfrage["app"] == "Transkription" and anfrage["von"] == "konto"

    offen = (await client.get("/api/v1/ablage/anfragen", headers=kopf)).json()
    assert [a["id"] for a in offen] == [anfrage["id"]]
    assert (await client.post(f"/api/v1/ablage/anfragen/{anfrage['id']}/annehmen", headers=kopf)).json()["zustand"] == "laeuft"
    mit = _mit(kopf, anfrage["id"])

    # genau diese Datei lesen, ihre Begleiter schreiben, sonst nichts
    assert (await client.get(f"/api/v1/ablage/knoten/{ton}/inhalt", headers=mit)).content == b"RIFF-ton"
    assert (await client.get(f"/api/v1/ablage/knoten/{text}/inhalt", headers=mit)).status_code == 404
    r = await client.put(f"/api/v1/ablage/knoten/{ton}/begleiter/transkript", params={"zusatz": ".transkript.json"},
                         content=b"{}", headers={**mit, "Content-Type": "application/json"})
    assert r.status_code == 200, r.text
    transkript = r.json()
    assert transkript["name"] == "Runde.transkript.json" and transkript["recht"] == "schreiben"
    r = await client.put(f"/api/v1/ablage/knoten/{ton}/begleiter/transkript", params={"zusatz": ".transkript.json"},
                         content=b'{"v":2}', headers={**mit, "Content-Type": "application/json", "If-Match": transkript["etag"]})
    assert r.status_code == 200, r.text
    # eine neue Version per Kennung zählt das Recht an der Datei selbst (nicht im Ordner)
    r = await client.put(f"/api/v1/ablage/knoten/{transkript['id']}/inhalt", content=b'{"v":3}',
                         headers={**mit, "Content-Type": "application/json", "If-Match": r.json()["etag"]})
    assert r.status_code == 200, r.text
    assert (await client.put(f"/api/v1/ablage/knoten/{text}/inhalt", content=b"x",
                             headers={**mit, "If-Match": "egal"})).status_code == 404
    r = await client.put(f"/api/v1/ablage/knoten/{text}/begleiter/sprache", params={"zusatz": ".sprache.mp3"},
                         content=b"x", headers=mit)
    assert r.status_code == 404
    r = await client.put("/api/v1/ablage/datei", params={"pfad": "Besprechungen/frei.txt"}, content=b"x", headers=mit)
    assert r.status_code in (403, 404)

    r = await client.patch(f"/api/v1/ablage/anfragen/{anfrage['id']}", json={"fortschritt": 0.5}, headers=kopf)
    assert r.status_code == 200 and r.json()["fortschritt"] == 0.5
    r = await client.patch(f"/api/v1/ablage/anfragen/{anfrage['id']}",
                           json={"zustand": "fertig", "ergebnis_id": transkript["id"]}, headers=kopf)
    assert r.status_code == 200 and r.json()["ergebnis_name"] == "Runde.transkript.json"

    # danach ist das Recht weg
    assert (await client.get(f"/api/v1/ablage/knoten/{ton}/inhalt", headers=mit)).status_code == 403
    assert (await client.get(f"/api/v1/ablage/knoten/{ton}/inhalt", headers=kopf)).status_code == 404
    liste = (await client.get("/api/v1/anfragen", headers=sitzung)).json()
    assert [(a["zustand"], a["ergebnis_name"]) for a in liste] == [("fertig", "Runde.transkript.json")]
    # die Datei hat jetzt ihren Begleiter, die Aktion heißt Neu transkribieren
    aktionen = (await client.get(f"/api/v1/dateien/{ton}/aktionen", headers=sitzung)).json()
    assert (aktionen[0]["titel"], aktionen[0]["erneut"]) == ("Neu transkribieren", True)
    # am Begleiter gibt es das Öffnen seiner Rolle, und es gilt für die Hauptdatei
    am_begleiter = (await client.get(f"/api/v1/dateien/{transkript['id']}/aktionen", headers=sitzung)).json()
    assert [(a["kennung"], a["knoten_id"]) for a in am_begleiter] == [("oeffnen", ton)]


async def test_abbrechen_beendet_das_recht(umgebung):
    client, sitzung = umgebung
    kopf, _, ton, _ = await _aufbau(client, sitzung)
    anfrage = (await _stellen(client, sitzung, ton))["anfrage"]
    await client.post(f"/api/v1/ablage/anfragen/{anfrage['id']}/annehmen", headers=kopf)
    assert (await client.delete(f"/api/v1/anfragen/{anfrage['id']}", headers=sitzung)).status_code == 204
    r = await client.patch(f"/api/v1/ablage/anfragen/{anfrage['id']}", json={"fortschritt": 0.2}, headers=kopf)
    assert r.status_code == 409
    assert (await client.get(f"/api/v1/ablage/knoten/{ton}", headers=_mit(kopf, anfrage["id"]))).status_code == 403
    assert (await client.post("/api/v1/anfragen/aufraeumen", headers=sitzung)).status_code == 204
    assert (await client.get("/api/v1/anfragen", headers=sitzung)).json() == []


async def test_abgelaufene_anfrage_gibt_kein_recht(umgebung, pool):
    client, sitzung = umgebung
    kopf, _, ton, _ = await _aufbau(client, sitzung)
    anfrage = (await _stellen(client, sitzung, ton))["anfrage"]
    async with pool.connection() as conn:
        await conn.execute("UPDATE anfrage SET gueltig_bis = now() - interval '1 minute' WHERE id=%s", (anfrage["id"],))
    assert (await client.get(f"/api/v1/ablage/knoten/{ton}", headers=_mit(kopf, anfrage["id"]))).status_code == 403
    assert (await client.get("/api/v1/ablage/anfragen", headers=kopf)).json() == []
    liste = (await client.get("/api/v1/anfragen", headers=sitzung)).json()
    assert [(a["zustand"], a["meldung"]) for a in liste] == [("fehler", "abgelaufen")]


async def test_fremde_anfrage_gilt_nicht(umgebung):
    client, sitzung = umgebung
    _, _, ton, _ = await _aufbau(client, sitzung)
    _, andere = await zugang(client, sitzung, "Stimmenausgabe")
    anfrage = (await _stellen(client, sitzung, ton))["anfrage"]
    assert (await client.get(f"/api/v1/ablage/knoten/{ton}", headers=_mit(andere, anfrage["id"]))).status_code == 403
    assert (await client.get(f"/api/v1/ablage/knoten/{ton}", headers=_mit(andere, "kein-uuid"))).status_code == 403


async def test_abholen_wacht_bei_neuer_anfrage_auf(umgebung):
    client, sitzung = umgebung
    kopf, _, ton, _ = await _aufbau(client, sitzung)
    beginn = time.monotonic()
    warten = asyncio.create_task(client.get("/api/v1/ablage/anfragen", params={"warten": 20}, headers=kopf))
    await asyncio.sleep(0.5)
    await _stellen(client, sitzung, ton)
    r = await warten
    assert len(r.json()) == 1 and time.monotonic() - beginn < 5


async def test_ohne_anfrage_kein_warten_ohne_ende(umgebung):
    client, sitzung = umgebung
    kopf, _, _, _ = await _aufbau(client, sitzung)
    beginn = time.monotonic()
    assert (await client.get("/api/v1/ablage/anfragen", params={"warten": 1}, headers=kopf)).json() == []
    assert 0.9 < time.monotonic() - beginn < 4


async def test_oeffnen_fuehrt_in_die_app(umgebung):
    client, sitzung = umgebung
    kopf, _, ton, _ = await _aufbau(client, sitzung)
    neu = await _stellen(client, sitzung, ton, "oeffnen")
    assert neu["ziel"] == f"https://192.168.178.49:8631/anfrage/{neu['anfrage']['id']}"
    assert (await client.get("/api/v1/ablage/anfragen", headers=kopf)).json() == []        # nicht im Hintergrund
    assert (await client.get("/api/v1/anfragen", headers=sitzung)).json() == []             # und nicht in den Vorgängen
    r = await client.post(f"/api/v1/ablage/anfragen/{neu['anfrage']['id']}/annehmen", headers=kopf)
    assert r.json()["zustand"] == "laeuft"
    r = await client.get(f"/api/v1/ablage/knoten/{ton}/inhalt", headers=_mit(kopf, neu["anfrage"]["id"]))
    assert r.status_code == 200


async def test_weitergabe_an_eine_andere_app(umgebung):
    client, sitzung = umgebung
    kopf, _, ton, _ = await _aufbau(client, sitzung)
    z, vertonung = await zugang(client, sitzung, "Vertonung")
    eigen = next(r["knoten_id"] for r in z["rechte"] if r["pfad"] == "Apps/Vertonung")
    film = await datei(client, sitzung, "Film.wav", b"RIFF-film", eigen)
    r = await client.post("/api/v1/ablage/anfragen", json={"app": "Transkription", "aktion": "transkribieren",
                                                           "knoten_id": film, "optionen": {"sprache": "en"}},
                          headers=vertonung)
    assert r.status_code == 200, r.text
    assert (r.json()["anfrage"]["von"], r.json()["anfrage"]["app"]) == ("Vertonung", "Transkription")
    # die Optionen kommen unverändert bei der angefragten App an
    offen = (await client.get("/api/v1/ablage/anfragen", headers=kopf)).json()
    assert [a["optionen"] for a in offen] == [{"sprache": "en"}]
    # den Stand liest auch, wer weitergegeben hat; eine dritte App nicht
    weiter_id = r.json()["anfrage"]["id"]
    assert (await client.get(f"/api/v1/ablage/anfragen/{weiter_id}", headers=vertonung)).json()["zustand"] == "wartet"
    _, dritte = await zugang(client, sitzung, "Dritte")
    assert (await client.get(f"/api/v1/ablage/anfragen/{weiter_id}", headers=dritte)).status_code == 404
    # Namen von Optionen sind Kennungen
    r = await client.post("/api/v1/ablage/anfragen", json={"app": "Transkription", "aktion": "transkribieren",
                                                           "knoten_id": film, "optionen": {"Sprache!": "en"}},
                          headers=vertonung)
    assert r.status_code == 422
    # eine Datei, die Vertonung nicht sehen darf, gibt sie auch nicht weiter
    r = await client.post("/api/v1/ablage/anfragen", json={"app": "Transkription", "aktion": "transkribieren",
                                                           "knoten_id": ton}, headers=vertonung)
    assert r.status_code == 404

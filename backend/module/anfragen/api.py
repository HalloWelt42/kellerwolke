"""Aktionen der Apps und Anfragen (siehe dienst.py).

Für das Konto (Sitzung): passende Aktionen einer Datei, Anfrage stellen, Anfragen ansehen, abbrechen, aufräumen.
Für Apps (App-Schlüssel, unter /api/v1/ablage): Aktionen melden, offene Anfragen abholen (lange Abfrage), annehmen,
Stand melden, an eine andere App weitergeben. Beim Lesen und Schreiben beruft sich die App mit dem Kopf
`X-Kellerwolke-Anfrage` auf eine offene Anfrage.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.abhaengig import aktuelle_app, aktueller_benutzer, app_mit_anmeldung, hole_ablage, hole_anfragen, hole_speicher
from app.inhaltstyp import inhaltstyp_aus_name
from module.ablage.dienst import KeinSchreibrecht, Unsichtbar
from module.anfragen.dienst import AktionPasstNicht, AnfrageUngueltig, OhneAdresse
from module.anfragen.modelle import (
    AktionAus,
    AktionEingabe,
    AktionenMeldung,
    AnfrageAus,
    AnfrageEingabe,
    AnfrageNeuAus,
    StandEingabe,
    WahlEingabe,
    WahlSeite,
    WeitergabeEingabe,
)

router = APIRouter(prefix="/api/v1", tags=["anfragen"])
router_app = APIRouter(prefix="/api/v1/ablage", tags=["ablage"])


def _fehler(f: Exception) -> HTTPException:
    if isinstance(f, (AnfrageUngueltig,)):
        return HTTPException(status_code=409, detail=str(f))
    if isinstance(f, (OhneAdresse,)):
        return HTTPException(status_code=409, detail=str(f))
    if isinstance(f, Unsichtbar):
        return HTTPException(status_code=404, detail=str(f))
    if isinstance(f, KeinSchreibrecht):
        return HTTPException(status_code=403, detail=str(f))
    return HTTPException(status_code=422, detail=str(f))


_FEHLER = (AnfrageUngueltig, AktionPasstNicht, OhneAdresse, Unsichtbar, KeinSchreibrecht, ValueError)


# --- Konto ------------------------------------------------------------------------------------------------------

@router.get("/dateien/{knoten_id}/aktionen", response_model=list[AktionAus])
async def aktionen(knoten_id: UUID, benutzer=Depends(aktueller_benutzer), anfragen=Depends(hole_anfragen)):
    """Was die Apps des Kontos mit dieser Datei können."""
    return await anfragen.aktionen_fuer(benutzer["id"], knoten_id)


@router.get("/anfragen", response_model=list[AnfrageAus])
async def liste(benutzer=Depends(aktueller_benutzer), anfragen=Depends(hole_anfragen)):
    """Anfragen an Apps: offene und die der letzten 24 Stunden."""
    return await anfragen.liste_konto(benutzer["id"])


@router.post("/anfragen", response_model=AnfrageNeuAus)
async def stellen(eingabe: AnfrageEingabe, benutzer=Depends(aktueller_benutzer), anfragen=Depends(hole_anfragen)):
    try:
        anfrage, ziel = await anfragen.stellen(benutzer["id"], eingabe.zugang_id, eingabe.aktion, eingabe.knoten_id)
    except _FEHLER as f:
        raise _fehler(f) from None
    return {"anfrage": anfrage, "ziel": ziel}


@router.delete("/anfragen/{anfrage_id}", status_code=204)
async def abbrechen(anfrage_id: UUID, benutzer=Depends(aktueller_benutzer), anfragen=Depends(hole_anfragen)):
    if not await anfragen.abbrechen(benutzer["id"], anfrage_id):
        raise HTTPException(status_code=404, detail="Keine offene Anfrage")


@router.post("/anfragen/aufraeumen", status_code=204)
async def aufraeumen(benutzer=Depends(aktueller_benutzer), anfragen=Depends(hole_anfragen)):
    await anfragen.aufraeumen(benutzer["id"])


# --- Apps -------------------------------------------------------------------------------------------------------

@router_app.put("/aktionen", response_model=list[AktionEingabe])
async def aktionen_melden(eingabe: AktionenMeldung, akteur=Depends(aktuelle_app), anfragen=Depends(hole_anfragen)):
    """Die App meldet ihre Aktionen (ersetzt die Liste ganz) und die Adresse ihrer Oberfläche."""
    return await anfragen.aktionen_melden(akteur, eingabe.adresse, [a.model_dump() for a in eingabe.aktionen])


@router_app.get("/anfragen", response_model=list[AnfrageAus])
async def offene(warten: float = Query(0, ge=0, le=30, description="so lange auf eine neue Anfrage warten (Sekunden)"),
                 akteur=Depends(aktuelle_app), anfragen=Depends(hole_anfragen)):
    """Wartende Anfragen an diese App, älteste zuerst; zugleich ihr Lebenszeichen."""
    return await anfragen.offene_holen(akteur, warten)


@router_app.get("/anfragen/{anfrage_id}", response_model=AnfrageAus)
async def eine(anfrage_id: UUID, akteur=Depends(aktuelle_app), anfragen=Depends(hole_anfragen)):
    try:
        return await anfragen.anfrage_der_app(akteur, anfrage_id)
    except _FEHLER as f:
        raise HTTPException(status_code=404, detail=str(f)) from None


@router_app.post("/anfragen/{anfrage_id}/annehmen", response_model=AnfrageAus)
async def annehmen(anfrage_id: UUID, akteur=Depends(aktuelle_app), anfragen=Depends(hole_anfragen)):
    try:
        return await anfragen.annehmen(akteur, anfrage_id)
    except _FEHLER as f:
        raise _fehler(f) from None


@router_app.patch("/anfragen/{anfrage_id}", response_model=AnfrageAus)
async def stand(anfrage_id: UUID, eingabe: StandEingabe, akteur=Depends(aktuelle_app), anfragen=Depends(hole_anfragen)):
    """Fortschritt und Ende melden; ist die Anfrage abgebrochen oder abgelaufen, kommt 409 und die App hört auf."""
    try:
        return await anfragen.stand_setzen(akteur, anfrage_id, eingabe.zustand, eingabe.fortschritt, eingabe.meldung,
                                           eingabe.ergebnis_id)
    except _FEHLER as f:
        raise _fehler(f) from None


@router_app.post("/anfragen", response_model=AnfrageNeuAus)
async def weitergeben(eingabe: WeitergabeEingabe, akteur=Depends(aktuelle_app), ablage=Depends(hole_ablage),
                      anfragen=Depends(hole_anfragen)):
    """Eine Anfrage an eine andere App desselben Kontos (etwa Vertonung an Transkription). Wer weitergibt, muss die
    Datei lesen und neben ihr schreiben dürfen."""
    try:
        await ablage.darf_weitergeben(akteur, eingabe.knoten_id)
        zugang_id = await anfragen.zugang_der_app(akteur.benutzer_id, eingabe.app)
        if zugang_id is None:
            raise Unsichtbar(f"Keine App {eingabe.app}")
        anfrage, ziel = await anfragen.stellen(akteur.benutzer_id, zugang_id, eingabe.aktion, eingabe.knoten_id,
                                               von=akteur.app, optionen=eingabe.optionen)
    except _FEHLER as f:
        raise _fehler(f) from None
    return {"anfrage": anfrage, "ziel": ziel}


# --- Dateiwahl in einer App -------------------------------------------------------------------------------------
# Mit App-Schlüssel UND der Anmeldung des Menschen an dieser App: blättern zeigt nur Namen und Eckdaten, die Wahl
# stellt eine Anfrage; erst dann darf die App die Datei lesen (und nur sie, solange die Anfrage offen ist).

@router_app.get("/wahl", response_model=WahlSeite)
async def wahl(ordner: UUID | None = None, akteur=Depends(app_mit_anmeldung), speicher=Depends(hole_speicher)):
    benutzer_id = akteur.benutzer_id
    kette = [{"id": None, "name": "Meine Dateien"}]
    if ordner is not None:
        knoten = await speicher.lebender_knoten(benutzer_id, ordner)
        if not knoten or knoten["typ"] != "ordner":
            raise HTTPException(status_code=404, detail="Ordner nicht gefunden")
        kette += [{"id": a["id"], "name": a["name"]} for a in (await speicher.ahnen(benutzer_id, ordner) or [])]
        kette.append({"id": knoten["id"], "name": knoten["name"]})
    eintraege = [{**k, "inhaltstyp": inhaltstyp_aus_name(k["name"]) if k["typ"] == "datei" else None}
                 for k in await speicher.kinder(benutzer_id, ordner) if k["typ"] in ("ordner", "datei")]
    return {"kette": kette, "eintraege": eintraege}


@router_app.post("/wahl", response_model=AnfrageNeuAus)
async def gewaehlt(eingabe: WahlEingabe, akteur=Depends(app_mit_anmeldung), anfragen=Depends(hole_anfragen)):
    """Der Mensch hat in der App eine Datei gewählt: Anfrage an diese App für die Aktion."""
    try:
        anfrage, ziel = await anfragen.stellen(akteur.benutzer_id, akteur.zugang_id, eingabe.aktion, eingabe.knoten_id)
    except _FEHLER as f:
        raise _fehler(f) from None
    return {"anfrage": anfrage, "ziel": ziel}

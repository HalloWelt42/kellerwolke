"""Gekoppelte Geräte (siehe dienst.py).

Am Rechner: `POST /api/v1/geraete/kopplung` erzeugt einen Code, `GET .../kopplung/{id}` sagt, ob ein Gerät ihn
eingelöst hat. Auf dem Gerät, ohne Anmeldung: `POST /api/v1/geraete/koppeln` mit Code, Name und Art liefert den
Schlüssel; er geht danach im Kopf `X-Kellerwolke-Sitzung` mit wie ein Sitzungs-Token.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator

from app.abhaengig import absender, aktueller_benutzer, hole_geraete
from module.auth.modelle import BenutzerAus
from module.geraete.dienst import CodeUngueltig, GeraetNichtGefunden, ZuVieleVersuche, geraetename_pruefen

router = APIRouter(prefix="/api/v1/geraete", tags=["geraete"])

GeraeteArt = Literal["webapp", "browser"]


class GeraetAus(BaseModel):
    id: UUID
    name: str
    art: GeraeteArt
    gekoppelt_am: datetime
    zuletzt_am: datetime | None
    zuletzt_adresse: str | None
    app: str | None = None   # gekoppelt für eine eigene App (gilt nur dort zur Anmeldung)
    dieses: bool = False  # das Gerät, das gerade fragt


class KopplungAus(BaseModel):
    id: UUID
    code: str | None = None  # nur beim Erzeugen
    ablauf: datetime
    stand: Literal["wartet", "gekoppelt", "abgelaufen"]
    geraet: GeraetAus | None = None


class KoppelnEingabe(BaseModel):
    code: str
    name: str
    art: GeraeteArt
    fuer_app: str | None = Field(None, min_length=1, max_length=60)   # Gerät koppelt eine eigene App, nicht die Kellerwolke

    @field_validator("name")
    @classmethod
    def _name(cls, wert: str) -> str:
        return geraetename_pruefen(wert)


class KoppelnAntwort(BaseModel):
    schluessel: str
    geraet: GeraetAus
    benutzer: BenutzerAus


class UmbenennenEingabe(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def _name(cls, wert: str) -> str:
        return geraetename_pruefen(wert)


def _geraet(zeile: dict, benutzer: dict | None = None) -> GeraetAus:
    dieses = benutzer is not None and str(benutzer.get("geraet_id") or "") == str(zeile["id"])
    return GeraetAus(**{k: zeile[k] for k in ("id", "name", "art", "gekoppelt_am", "zuletzt_am", "zuletzt_adresse")},
                     app=zeile.get("app"), dieses=dieses)


def _kopplung(zeile: dict, geraet: dict | None, code: str | None = None) -> KopplungAus:
    if zeile["eingeloest_am"]:
        stand = "gekoppelt"
    elif zeile["ablauf"] <= datetime.now(zeile["ablauf"].tzinfo):
        stand = "abgelaufen"
    else:
        stand = "wartet"
    return KopplungAus(id=zeile["id"], code=code, ablauf=zeile["ablauf"], stand=stand,
                       geraet=_geraet(geraet) if geraet else None)


@router.get("", response_model=list[GeraetAus])
async def liste(benutzer=Depends(aktueller_benutzer), geraete=Depends(hole_geraete)):
    return [_geraet(g, benutzer) for g in await geraete.liste(benutzer["id"])]


@router.get("/dieses", response_model=GeraetAus)
async def dieses(benutzer=Depends(aktueller_benutzer), geraete=Depends(hole_geraete)):
    """Das Gerät, das gerade fragt; 404 bei einer Anmeldung mit Passwort."""
    if not benutzer.get("geraet_id"):
        raise HTTPException(status_code=404, detail="Angemeldet mit Passwort, nicht als gekoppeltes Gerät")
    return _geraet(await geraete.holen(benutzer["id"], benutzer["geraet_id"]), benutzer)


@router.post("/kopplung", response_model=KopplungAus, status_code=201)
async def kopplung_starten(benutzer=Depends(aktueller_benutzer), geraete=Depends(hole_geraete)):
    zeile, code = await geraete.kopplung_starten(benutzer["id"])
    return _kopplung(zeile, None, code)


@router.get("/kopplung/{kopplung_id}", response_model=KopplungAus)
async def kopplung_stand(kopplung_id: UUID, benutzer=Depends(aktueller_benutzer), geraete=Depends(hole_geraete)):
    try:
        return _kopplung(*await geraete.kopplung_stand(benutzer["id"], kopplung_id))
    except GeraetNichtGefunden:
        raise HTTPException(status_code=404, detail="Kopplung nicht gefunden")


@router.delete("/kopplung/{kopplung_id}", status_code=204)
async def kopplung_abbrechen(kopplung_id: UUID, benutzer=Depends(aktueller_benutzer), geraete=Depends(hole_geraete)):
    try:
        await geraete.kopplung_abbrechen(benutzer["id"], kopplung_id)
    except GeraetNichtGefunden:
        raise HTTPException(status_code=404, detail="Kopplung nicht gefunden")
    return Response(status_code=204)


@router.post("/koppeln", response_model=KoppelnAntwort, status_code=201)
async def koppeln(eingabe: KoppelnEingabe, request: Request, geraete=Depends(hole_geraete)):
    """Ohne Anmeldung: der Code ist der Nachweis."""
    try:
        geraet, schluessel, benutzer = await geraete.koppeln(eingabe.code, eingabe.name, eingabe.art,
                                                             absender(request) or "", eingabe.fuer_app)
    except ZuVieleVersuche as f:
        raise HTTPException(status_code=429, detail=str(f), headers={"Retry-After": str(f.sekunden)})
    except CodeUngueltig:
        raise HTTPException(status_code=404, detail="Dieser Code gilt nicht (mehr). Er gilt zehn Minuten und nur "
                                                    "einmal; erzeug am Rechner einen neuen.")
    return KoppelnAntwort(schluessel=schluessel, geraet=_geraet(geraet, {"geraet_id": geraet["id"]}),
                          benutzer=BenutzerAus.model_validate(benutzer))


@router.patch("/{geraet_id}", response_model=GeraetAus)
async def umbenennen(geraet_id: UUID, eingabe: UmbenennenEingabe, benutzer=Depends(aktueller_benutzer),
                     geraete=Depends(hole_geraete)):
    try:
        return _geraet(await geraete.umbenennen(benutzer["id"], geraet_id, eingabe.name), benutzer)
    except GeraetNichtGefunden:
        raise HTTPException(status_code=404, detail="Gerät nicht gefunden")


@router.delete("/{geraet_id}", status_code=204)
async def trennen(geraet_id: UUID, benutzer=Depends(aktueller_benutzer), geraete=Depends(hole_geraete)):
    try:
        await geraete.trennen(benutzer["id"], geraet_id)
    except GeraetNichtGefunden:
        raise HTTPException(status_code=404, detail="Gerät nicht gefunden")
    return Response(status_code=204)

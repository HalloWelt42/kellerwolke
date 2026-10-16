"""Ablage-Schnittstelle für eigene Apps (ohne Browser). Anmeldung mit dem App-Schlüssel als
`Authorization: Bearer kw_app_...`; jede Anfrage wird gegen die Rechte des Zugangs geprüft."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from app.abhaengig import aktuelle_app, hole_ablage
from module.ablage.dienst import KeinSchreibrecht, Unsichtbar
from module.appzugang.modelle import RechtAus
from module.speicher.api import bereich_aus_kopf, dateiname_kopf

router = APIRouter(prefix="/api/v1/ablage", tags=["ablage"])


class AblageKnotenAus(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: UUID
    parent_id: UUID | None = None
    name: str
    typ: str
    pfad: str
    recht: Literal["lesen", "schreiben"]
    etag: str | None = None
    groesse: int | None = None
    erstellt_am: datetime
    geaendert_am: datetime


class IchAus(BaseModel):
    app: str
    konto: str
    rechte: list[RechtAus]


class OrdnerPfadEingabe(BaseModel):
    pfad: str = Field(min_length=1, max_length=4000)


def _fehler(f: Exception) -> HTTPException:
    if isinstance(f, Unsichtbar):
        return HTTPException(status_code=404, detail=str(f))
    if isinstance(f, KeinSchreibrecht):
        return HTTPException(status_code=403, detail=str(f))
    if isinstance(f, FileExistsError):
        return HTTPException(status_code=409, detail=str(f))
    return HTTPException(status_code=422, detail=str(f))


_FEHLER = (Unsichtbar, KeinSchreibrecht, FileExistsError, ValueError)


@router.get("/ich", response_model=IchAus)
async def ich(akteur=Depends(aktuelle_app), ablage=Depends(hole_ablage)):
    return await ablage.ich(akteur)


@router.get("/knoten/{knoten_id}", response_model=AblageKnotenAus)
async def knoten(knoten_id: UUID, akteur=Depends(aktuelle_app), ablage=Depends(hole_ablage)):
    try:
        return await ablage.knoten(akteur, knoten_id)
    except _FEHLER as f:
        raise _fehler(f) from None


@router.get("/pfad", response_model=AblageKnotenAus)
async def pfad(pfad: str = Query(min_length=1, max_length=4000), akteur=Depends(aktuelle_app),
               ablage=Depends(hole_ablage)):
    try:
        return await ablage.pfad_aufloesen(akteur, pfad)
    except _FEHLER as f:
        raise _fehler(f) from None


@router.get("/knoten/{knoten_id}/kinder", response_model=list[AblageKnotenAus])
async def kinder(knoten_id: UUID, ab: int = Query(0, ge=0), anzahl: int = Query(200, ge=1, le=500),
                 akteur=Depends(aktuelle_app), ablage=Depends(hole_ablage)):
    try:
        return await ablage.kinder(akteur, knoten_id, ab, anzahl)
    except _FEHLER as f:
        raise _fehler(f) from None


@router.post("/ordner", response_model=AblageKnotenAus)
async def ordner(eingabe: OrdnerPfadEingabe, akteur=Depends(aktuelle_app), ablage=Depends(hole_ablage)):
    try:
        return await ablage.ordner_anlegen(akteur, eingabe.pfad)
    except _FEHLER as f:
        raise _fehler(f) from None


@router.get("/knoten/{knoten_id}/inhalt")
async def inhalt(knoten_id: UUID, request: Request, akteur=Depends(aktuelle_app), ablage=Depends(hole_ablage)):
    try:
        knoten, gesamt = await ablage.datei_kopf(akteur, knoten_id)
    except _FEHLER as f:
        raise _fehler(f) from None
    kopf = {"Content-Disposition": dateiname_kopf(knoten["name"]), "ETag": knoten["etag"] or "", "Accept-Ranges": "bytes"}
    start, ende = bereich_aus_kopf(request.headers.get("range"), gesamt)
    if start is None:
        kopf["Content-Length"] = str(gesamt)
        return StreamingResponse(ablage.datei_stroemen(akteur, knoten_id), media_type="application/octet-stream", headers=kopf)
    kopf["Content-Range"] = f"bytes {start}-{ende}/{gesamt}"
    kopf["Content-Length"] = str(ende - start + 1)
    return StreamingResponse(ablage.datei_stroemen(akteur, knoten_id, start, ende - start + 1), status_code=206,
                             media_type="application/octet-stream", headers=kopf)

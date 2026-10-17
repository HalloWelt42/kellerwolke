"""Sync-Router: liefert das Aenderungs-Journal pro Nutzer (Grundlage fuer einen
kuenftigen Geraete-Abgleich). Der eigentliche Sync-Client ist noch nicht gebaut.
"""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.abhaengig import aktueller_benutzer, hole_speicher
from module.sync.modelle import AenderungAus

router = APIRouter(prefix="/api/v1/sync", tags=["sync"])


@router.get("/journal", response_model=list[AenderungAus])
async def journal(seit: int = Query(0, ge=0), anzahl: int = Query(1000, ge=1, le=5000),
                  benutzer=Depends(aktueller_benutzer), speicher=Depends(hole_speicher)):
    eintraege = await speicher.journal_seit(benutzer["id"], seit, anzahl)
    return [AenderungAus.model_validate(e) for e in eintraege]


class StandAus(BaseModel):
    seq: int  # letzte vergebene Nummer des Kontos; wer ab hier beobachtet, verpasst nichts und lädt nichts nach


@router.get("/stand", response_model=StandAus)
async def stand(benutzer=Depends(aktueller_benutzer), speicher=Depends(hole_speicher)):
    return StandAus(seq=await speicher.journal_stand(benutzer["id"]))

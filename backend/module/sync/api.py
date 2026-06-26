"""Sync-Router: liefert das Aenderungs-Journal pro Nutzer (Grundlage fuer einen
kuenftigen Geraete-Abgleich). Der eigentliche Sync-Client ist noch nicht gebaut.
"""

from fastapi import APIRouter, Depends, Query

from app.abhaengig import aktueller_benutzer, hole_speicher
from module.sync.modelle import AenderungAus

router = APIRouter(prefix="/api/v1/sync", tags=["sync"])


@router.get("/journal", response_model=list[AenderungAus])
async def journal(seit: int = Query(0, ge=0), benutzer=Depends(aktueller_benutzer),
                  speicher=Depends(hole_speicher)):
    eintraege = await speicher.journal_seit(benutzer["id"], seit)
    return [AenderungAus.model_validate(e) for e in eintraege]

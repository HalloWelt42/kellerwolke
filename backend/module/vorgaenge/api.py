"""Vorgaenge-Router: laufende und abgeschlossene Hintergrund-Jobs des Nutzers
auflisten, abbrechen und aufraeumen. Jede Route ist streng auf den eigenen
Nutzer gefiltert (Isolation)."""

from fastapi import APIRouter, Depends, HTTPException

from app.abhaengig import aktueller_benutzer, hole_vorgaenge
from module.vorgaenge.modelle import VorgangAus

router = APIRouter(prefix="/api/v1/vorgaenge", tags=["vorgaenge"])


@router.get("", response_model=list[VorgangAus])
async def liste(benutzer=Depends(aktueller_benutzer), vorgaenge=Depends(hole_vorgaenge)):
    return [
        VorgangAus(
            id=v.id,
            art=v.art,
            titel=v.titel,
            status=v.status,
            erledigt=v.erledigt,
            gesamt=v.gesamt,
            fehler=v.fehler,
        )
        for v in vorgaenge.liste(benutzer["id"])
    ]


@router.post("/aufraeumen", status_code=204)
async def aufraeumen(benutzer=Depends(aktueller_benutzer), vorgaenge=Depends(hole_vorgaenge)):
    vorgaenge.aufraeumen(benutzer["id"])


@router.post("/{vorgang_id}/abbrechen", status_code=204)
async def abbrechen(
    vorgang_id: str,
    benutzer=Depends(aktueller_benutzer),
    vorgaenge=Depends(hole_vorgaenge),
):
    if not vorgaenge.abbrechen(benutzer["id"], vorgang_id):
        raise HTTPException(status_code=404, detail="Nicht gefunden")

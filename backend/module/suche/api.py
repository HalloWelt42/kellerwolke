"""Such-Router: Volltextsuche fuer den angemeldeten Nutzer."""

from fastapi import APIRouter, Depends

from app.abhaengig import aktueller_benutzer, hole_suche
from module.speicher.modelle import KnotenAus

router = APIRouter(prefix="/api/v1/suche", tags=["suche"])


@router.get("", response_model=list[KnotenAus])
async def suchen(q: str, benutzer=Depends(aktueller_benutzer), suche=Depends(hole_suche)):
    treffer = await suche.suchen(benutzer["id"], q)
    return [KnotenAus.model_validate(t) for t in treffer]

"""Medien-Router: die baumweite Liste aller eigenen Medien für die Medienansicht. Vorschau, Vollbild und Wiedergabe
liefert der Inhalts-Router (module/inhalt/api.py)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.abhaengig import aktueller_benutzer, hole_speicher
from module.medien.arten import Medienart, medienart

router = APIRouter(prefix="/api/v1/medien", tags=["medien"])


class PfadteilAus(BaseModel):
    id: str
    name: str


class MediumAus(BaseModel):
    id: UUID
    name: str
    art: Medienart
    etag: str | None
    groesse: int | None
    geaendert_am: datetime
    pfad: list[PfadteilAus]


@router.get("/alle", response_model=list[MediumAus])
async def alle(benutzer=Depends(aktueller_benutzer), speicher=Depends(hole_speicher)):
    """Alle eigenen Medien im ganzen Baum, je mit Ordnerkette."""
    return [MediumAus(art=medienart(z["name"]), **z) for z in await speicher.medien_im_baum(benutzer["id"])]

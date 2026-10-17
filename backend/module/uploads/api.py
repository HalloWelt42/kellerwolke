"""Fortsetzbare Uploads (siehe dienst.py). Ablauf für einen Sender:

1. `POST /api/v1/uploads` mit Name, Zielordner, Größe (und auf Wunsch der Prüfsumme) - liefert die Kennung.
2. `PATCH /api/v1/uploads/{id}` je Teil, Kopf `Upload-Offset` = bisher empfangen, Körper = das Teil (roh).
3. Nach einer Unterbrechung `GET /api/v1/uploads/{id}`: `empfangen` sagt, wo es weitergeht.
4. Mit dem letzten Teil ist die Datei eingetragen; die Antwort trägt den Knoten.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator

from app.abhaengig import aktueller_benutzer, hole_speicher, hole_suche, hole_uploads, hole_vorgaenge
from app.config import EINSTELLUNGEN
from module.speicher.dienst import NameBelegt, PruefsummeFalsch, ZielUngueltig
from module.speicher.modelle import KnotenAus, sauberer_name
from module.suche.dienst import indizierung_starten
from module.uploads.dienst import FalscherVersatz, Upload, UploadLaeuft, UploadNichtGefunden, ZuViel

router = APIRouter(prefix="/api/v1/uploads", tags=["uploads"])


class UploadEingabe(BaseModel):
    name: str
    parent_id: UUID | None = None
    groesse: int = Field(ge=0)
    pruefsumme: str | None = Field(None, pattern=r"^[0-9a-f]{64}$", description="sha256 des ganzen Inhalts (hex)")

    @field_validator("name")
    @classmethod
    def _name(cls, wert: str) -> str:
        return sauberer_name(wert)


class UploadAus(BaseModel):
    id: UUID
    name: str
    parent_id: UUID | None
    groesse: int
    empfangen: int  # beim nächsten Teil als Upload-Offset senden
    erstellt_am: datetime
    zuletzt_am: datetime
    fertig: bool = False
    knoten: KnotenAus | None = None  # mit dem letzten Teil: die eingetragene Datei


def _aus(u: Upload, knoten: dict | None = None) -> UploadAus:
    return UploadAus(id=u.id, name=u.name, parent_id=u.parent_id, groesse=u.groesse,
                     empfangen=u.groesse if knoten else u.empfangen, erstellt_am=u.erstellt_am,
                     zuletzt_am=u.zuletzt_am, fertig=knoten is not None,
                     knoten=KnotenAus.model_validate(knoten) if knoten else None)


@router.post("", response_model=UploadAus, status_code=201)
async def anlegen(eingabe: UploadEingabe, benutzer=Depends(aktueller_benutzer), uploads=Depends(hole_uploads)):
    if eingabe.groesse > EINSTELLUNGEN.max_upload:
        raise HTTPException(status_code=413, detail="Datei zu groß")
    try:
        return _aus(await uploads.anlegen(benutzer["id"], eingabe.parent_id, eingabe.name, eingabe.groesse,
                                          eingabe.pruefsumme))
    except ZielUngueltig:
        raise HTTPException(status_code=404, detail="Zielordner nicht gefunden")


@router.get("", response_model=list[UploadAus])
async def liste(benutzer=Depends(aktueller_benutzer), uploads=Depends(hole_uploads)):
    """Offene Uploads des Kontos, etwa um nach einem Neustart der App fortzusetzen."""
    return [_aus(u) for u in await uploads.liste(benutzer["id"])]


@router.get("/{upload_id}", response_model=UploadAus)
async def stand(upload_id: UUID, benutzer=Depends(aktueller_benutzer), uploads=Depends(hole_uploads)):
    try:
        return _aus(await uploads.holen(benutzer["id"], upload_id))
    except UploadNichtGefunden:
        raise HTTPException(status_code=404, detail="Upload nicht gefunden")


@router.patch("/{upload_id}", response_model=UploadAus)
async def teil(upload_id: UUID, request: Request, benutzer=Depends(aktueller_benutzer), uploads=Depends(hole_uploads),
               speicher=Depends(hole_speicher), suche=Depends(hole_suche), vorgaenge=Depends(hole_vorgaenge)):
    kopf = request.headers.get("upload-offset", "")
    if not kopf.isdigit():
        raise HTTPException(status_code=428, detail="Kopf Upload-Offset fehlt (bisher empfangene Bytes)")
    try:
        u, knoten = await uploads.anhaengen(benutzer["id"], upload_id, int(kopf), request.stream(),
                                            EINSTELLUNGEN.max_upload)
    except UploadNichtGefunden:
        raise HTTPException(status_code=404, detail="Upload nicht gefunden")
    except FalscherVersatz as f:
        raise HTTPException(status_code=409, detail=str(f), headers={"Upload-Offset": str(f.empfangen)})
    except UploadLaeuft as f:
        raise HTTPException(status_code=409, detail=str(f))
    except ZuViel:
        raise HTTPException(status_code=413, detail="Das Teil geht über die angekündigte Größe hinaus")
    except ZielUngueltig:
        raise HTTPException(status_code=404, detail="Zielordner nicht gefunden")
    except NameBelegt as f:
        raise HTTPException(status_code=409, detail=str(f))
    except PruefsummeFalsch as f:
        raise HTTPException(status_code=422, detail=str(f))
    if knoten:
        indizierung_starten(vorgaenge, suche, speicher, benutzer["id"], knoten)
    return _aus(u, knoten)


@router.delete("/{upload_id}", status_code=204)
async def abbrechen(upload_id: UUID, benutzer=Depends(aktueller_benutzer), uploads=Depends(hole_uploads)):
    try:
        await uploads.abbrechen(benutzer["id"], upload_id)
    except UploadNichtGefunden:
        raise HTTPException(status_code=404, detail="Upload nicht gefunden")
    except UploadLaeuft as f:
        raise HTTPException(status_code=409, detail=str(f))
    return Response(status_code=204)

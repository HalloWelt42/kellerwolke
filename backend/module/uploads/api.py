"""Fortsetzbare Uploads (siehe dienst.py). Ablauf für einen Sender:

1. `POST /api/v1/uploads` mit Name, Zielordner, Größe (und auf Wunsch der Prüfsumme) - liefert die Kennung.
2. `PATCH /api/v1/uploads/{id}` je Teil, Kopf `Upload-Offset` = bisher empfangen, Körper = das Teil (roh).
3. Nach einer Unterbrechung `GET /api/v1/uploads/{id}`: `empfangen` sagt, wo es weitergeht.
4. Mit dem letzten Teil ist die Datei eingetragen; die Antwort trägt den Knoten.

Anmelden mit der Sitzung (Kopf X-Kellerwolke-Sitzung) oder als App mit ihrem Schlüssel (`Authorization: Bearer
kw_app_...`, KW-11). Eine App schreibt nur dort, wo sie Schreibrecht hat, und überschreibt eine vorhandene Datei nur
mit dem zuletzt gelesenen Stand (`etag`) oder legt nur neu an (`nur_neu`); geprüft wird beim Anlegen und noch einmal
mit dem letzten Teil. Ein Upload gehört dem, der ihn begonnen hat.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator

from app.abhaengig import aktuelle_app, aktueller_benutzer, hole_ablage, hole_speicher, hole_suche, hole_uploads, hole_vorgaenge
from app.config import EINSTELLUNGEN
from module.ablage.dienst import KeinSchreibrecht, Unsichtbar, VorbedingungFehlt
from module.appzugang.dienst import AppAkteur
from module.speicher.dienst import Gesperrt, NameBelegt, PruefsummeFalsch, VorbedingungVerletzt, ZielUngueltig
from module.speicher.modelle import KnotenAus, sauberer_name
from module.suche.dienst import indizierung_starten
from module.uploads.dienst import FalscherVersatz, Upload, UploadLaeuft, UploadNichtGefunden, ZuViel

router = APIRouter(prefix="/api/v1/uploads", tags=["uploads"])


class UploadEingabe(BaseModel):
    name: str
    parent_id: UUID | None = None
    groesse: int = Field(ge=0)
    pruefsumme: str | None = Field(None, pattern=r"^[0-9a-f]{64}$", description="sha256 des ganzen Inhalts (hex)")
    etag: str | None = Field(None, max_length=200, description="eine vorhandene Datei nur überschreiben, wenn sie "
                                                               "genau diesen Stand hat")
    nur_neu: bool = Field(False, description="nur neu anlegen, nie überschreiben")

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


@dataclass(frozen=True)
class Sender:
    """Wer hochlädt: die Anmeldung des Kontos oder eine App mit ihrem Schlüssel."""

    benutzer_id: UUID
    app: AppAkteur | None = None

    @property
    def zugang_id(self):
        return self.app.zugang_id if self.app else None


async def sender(request: Request) -> Sender:
    if request.headers.get("authorization", "").lower().startswith("bearer "):
        akteur = await aktuelle_app(request)
        return Sender(akteur.benutzer_id, akteur)
    benutzer = await aktueller_benutzer(request)
    return Sender(benutzer["id"])


def _fehler(f: Exception) -> HTTPException:
    if isinstance(f, (ZielUngueltig, Unsichtbar, UploadNichtGefunden)):
        return HTTPException(status_code=404, detail=str(f))
    if isinstance(f, KeinSchreibrecht):
        return HTTPException(status_code=403, detail=str(f))
    if isinstance(f, FalscherVersatz):
        return HTTPException(status_code=409, detail=str(f), headers={"Upload-Offset": str(f.empfangen)})
    if isinstance(f, (UploadLaeuft, NameBelegt, FileExistsError)):
        return HTTPException(status_code=409, detail=str(f))
    if isinstance(f, VorbedingungVerletzt):
        return HTTPException(status_code=412, detail=str(f))
    if isinstance(f, ZuViel):
        return HTTPException(status_code=413, detail="Das Teil geht über die angekündigte Größe hinaus")
    if isinstance(f, Gesperrt):
        return HTTPException(status_code=423, detail=str(f))
    if isinstance(f, VorbedingungFehlt):
        return HTTPException(status_code=428, detail=str(f))
    return HTTPException(status_code=422, detail=str(f))


_FEHLER = (ZielUngueltig, Unsichtbar, UploadNichtGefunden, KeinSchreibrecht, FalscherVersatz, UploadLaeuft, NameBelegt,
           FileExistsError, VorbedingungVerletzt, ZuViel, Gesperrt, VorbedingungFehlt, PruefsummeFalsch, ValueError)


def _aus(u: Upload, knoten: dict | None = None) -> UploadAus:
    return UploadAus(id=u.id, name=u.name, parent_id=u.parent_id, groesse=u.groesse,
                     empfangen=u.groesse if knoten else u.empfangen, erstellt_am=u.erstellt_am,
                     zuletzt_am=u.zuletzt_am, fertig=knoten is not None,
                     knoten=KnotenAus.model_validate(knoten) if knoten else None)


@router.post("", response_model=UploadAus, status_code=201)
async def anlegen(eingabe: UploadEingabe, request: Request, wer: Sender = Depends(sender),
                  uploads=Depends(hole_uploads)):
    if eingabe.groesse > EINSTELLUNGEN.max_upload:
        raise HTTPException(status_code=413, detail="Datei zu groß")
    try:
        if wer.app:
            await hole_ablage(request).upload_pruefen(wer.app, eingabe.parent_id, eingabe.name, eingabe.etag, eingabe.nur_neu)
        return _aus(await uploads.anlegen(wer.benutzer_id, eingabe.parent_id, eingabe.name, eingabe.groesse,
                                          eingabe.pruefsumme, wer.zugang_id, eingabe.etag, eingabe.nur_neu))
    except _FEHLER as f:
        raise _fehler(f) from None


@router.get("", response_model=list[UploadAus])
async def liste(wer: Sender = Depends(sender), uploads=Depends(hole_uploads)):
    """Offene Uploads dessen, der fragt (Anmeldung oder App), etwa um nach einem Neustart fortzusetzen."""
    return [_aus(u) for u in await uploads.liste(wer.benutzer_id, wer.zugang_id)]


@router.get("/{upload_id}", response_model=UploadAus)
async def stand(upload_id: UUID, wer: Sender = Depends(sender), uploads=Depends(hole_uploads)):
    try:
        return _aus(await uploads.holen(wer.benutzer_id, upload_id, wer.zugang_id))
    except UploadNichtGefunden:
        raise HTTPException(status_code=404, detail="Upload nicht gefunden")


@router.patch("/{upload_id}", response_model=UploadAus)
async def teil(upload_id: UUID, request: Request, wer: Sender = Depends(sender), uploads=Depends(hole_uploads),
               speicher=Depends(hole_speicher), suche=Depends(hole_suche), vorgaenge=Depends(hole_vorgaenge)):
    kopf = request.headers.get("upload-offset", "")
    if not kopf.isdigit():
        raise HTTPException(status_code=428, detail="Kopf Upload-Offset fehlt (bisher empfangene Bytes)")

    async def als_app(zeile, quelle, max_bytes):
        return await hole_ablage(request).upload_eintragen(wer.app, zeile, quelle, max_bytes)

    try:
        u, knoten = await uploads.anhaengen(wer.benutzer_id, upload_id, int(kopf), request.stream(),
                                            EINSTELLUNGEN.max_upload, wer.zugang_id, als_app if wer.app else None)
    except _FEHLER as f:
        raise _fehler(f) from None
    if knoten:
        indizierung_starten(vorgaenge, suche, speicher, wer.benutzer_id, knoten)
    return _aus(u, knoten)


@router.delete("/{upload_id}", status_code=204)
async def abbrechen(upload_id: UUID, wer: Sender = Depends(sender), uploads=Depends(hole_uploads)):
    try:
        await uploads.abbrechen(wer.benutzer_id, upload_id, wer.zugang_id)
    except _FEHLER as f:
        raise _fehler(f) from None
    return Response(status_code=204)

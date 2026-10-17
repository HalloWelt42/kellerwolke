"""App-Zugänge verwalten: das angemeldete Konto stellt Schlüssel für seine Apps aus und vergibt Rechte je Ordner."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.abhaengig import aktueller_benutzer, hole_appzugang
from module.appzugang.modelle import AktivEingabe, RechteEingabe, ZugangAus, ZugangEingabe, ZugangNeuAus

router = APIRouter(prefix="/api/v1/app-zugaenge", tags=["app-zugaenge"])


def _fehler(f: Exception) -> HTTPException:
    if isinstance(f, FileNotFoundError):
        return HTTPException(status_code=404, detail=str(f))
    if isinstance(f, FileExistsError):
        return HTTPException(status_code=409, detail=str(f))
    return HTTPException(status_code=422, detail=str(f))


@router.get("", response_model=list[ZugangAus])
async def liste(benutzer=Depends(aktueller_benutzer), dienst=Depends(hole_appzugang)):
    return await dienst.liste(benutzer["id"])


@router.post("", response_model=ZugangNeuAus)
async def anlegen(eingabe: ZugangEingabe, benutzer=Depends(aktueller_benutzer), dienst=Depends(hole_appzugang)):
    try:
        zugang, schluessel = await dienst.anlegen(benutzer["id"], eingabe.app)
    except (ValueError, FileExistsError) as f:
        raise _fehler(f) from None
    return ZugangNeuAus(zugang=zugang, schluessel=schluessel)


@router.post("/{zugang_id}/erneuern", response_model=ZugangNeuAus)
async def erneuern(zugang_id: UUID, benutzer=Depends(aktueller_benutzer), dienst=Depends(hole_appzugang)):
    try:
        schluessel = await dienst.erneuern(benutzer["id"], zugang_id)
    except FileNotFoundError as f:
        raise _fehler(f) from None
    return ZugangNeuAus(zugang=await dienst.zugang(benutzer["id"], zugang_id), schluessel=schluessel)


@router.patch("/{zugang_id}", response_model=ZugangAus)
async def aktiv_setzen(zugang_id: UUID, eingabe: AktivEingabe, benutzer=Depends(aktueller_benutzer),
                       dienst=Depends(hole_appzugang)):
    try:
        if eingabe.app is not None:
            await dienst.umbenennen(benutzer["id"], zugang_id, eingabe.app)
        if eingabe.aktiv is not None:
            return await dienst.aktiv_setzen(benutzer["id"], zugang_id, eingabe.aktiv)
        zugang = await dienst.zugang(benutzer["id"], zugang_id)
        if zugang is None:
            raise FileNotFoundError("Zugang nicht gefunden")
        return zugang
    except (FileNotFoundError, FileExistsError, ValueError) as f:
        raise _fehler(f) from None


@router.put("/{zugang_id}/rechte", response_model=ZugangAus)
async def rechte_setzen(zugang_id: UUID, eingabe: RechteEingabe, benutzer=Depends(aktueller_benutzer),
                        dienst=Depends(hole_appzugang)):
    try:
        return await dienst.rechte_setzen(benutzer["id"], zugang_id, [(r.knoten_id, r.recht) for r in eingabe.rechte])
    except (ValueError, FileNotFoundError) as f:
        raise _fehler(f) from None


@router.delete("/{zugang_id}", status_code=204)
async def loeschen(zugang_id: UUID, benutzer=Depends(aktueller_benutzer), dienst=Depends(hole_appzugang)):
    try:
        await dienst.loeschen(benutzer["id"], zugang_id)
    except FileNotFoundError as f:
        raise _fehler(f) from None

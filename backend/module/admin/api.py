"""Admin-Router: Familienkonten anlegen/verwalten, Quota setzen (nur Admins)."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.abhaengig import aktueller_admin, hole_auth, hole_speicher
from module.admin.modelle import BenutzerAnlegen, BenutzerUpdate, ExternQuelleEingabe
from module.auth.modelle import BenutzerAus
from module.speicher.modelle import KnotenAus

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.post("/externe-quelle", response_model=KnotenAus, status_code=201)
async def externe_quelle(eingabe: ExternQuelleEingabe, admin=Depends(aktueller_admin),
                         speicher=Depends(hole_speicher)):
    knoten = await speicher.externe_quelle_anlegen(
        eingabe.besitzer_id, eingabe.parent_id, eingabe.name, eingabe.pfad
    )
    return KnotenAus.model_validate(knoten)


@router.get("/benutzer", response_model=list[BenutzerAus])
async def liste(admin=Depends(aktueller_admin), auth=Depends(hole_auth)):
    return [BenutzerAus.model_validate(b) for b in await auth.liste_benutzer()]


@router.post("/benutzer", response_model=BenutzerAus, status_code=201)
async def anlegen(eingabe: BenutzerAnlegen, admin=Depends(aktueller_admin), auth=Depends(hole_auth)):
    benutzer = await auth.benutzer_anlegen(
        eingabe.name, eingabe.passwort, rolle=eingabe.rolle, kuerzel=eingabe.kuerzel
    )
    return BenutzerAus.model_validate(benutzer)


@router.patch("/benutzer/{benutzer_id}", status_code=204)
async def aktualisieren(benutzer_id: UUID, eingabe: BenutzerUpdate,
                        admin=Depends(aktueller_admin), auth=Depends(hole_auth)):
    try:
        await auth.benutzer_aktualisieren(
            benutzer_id, aktiv=eingabe.aktiv, quota_bytes=eingabe.quota_bytes, rolle=eingabe.rolle
        )
    except ValueError as f:
        raise HTTPException(status_code=409, detail=str(f))

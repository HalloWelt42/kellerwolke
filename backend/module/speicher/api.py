"""Datei-Router: Browsen, Upload, Download, Umbenennen, Verschieben, Papierkorb,
Versionen. Jede Route prueft die Eigentuemerschaft des Knotens (Isolation).
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from fastapi.responses import Response

from app.abhaengig import aktueller_benutzer, hole_speicher, hole_suche
from module.speicher.modelle import (
    KnotenAus,
    OrdnerEingabe,
    UmbenennenEingabe,
    VerschiebenEingabe,
    VersionAus,
)

router = APIRouter(prefix="/api/v1/dateien", tags=["dateien"])


@router.get("", response_model=list[KnotenAus])
async def auflisten(parent_id: UUID | None = None, benutzer=Depends(aktueller_benutzer),
                    speicher=Depends(hole_speicher)):
    if parent_id and not await speicher.knoten_des_nutzers(benutzer["id"], parent_id):
        raise HTTPException(status_code=404, detail="Ordner nicht gefunden")
    return [KnotenAus.model_validate(k) for k in await speicher.kinder(benutzer["id"], parent_id)]


@router.get("/papierkorb", response_model=list[KnotenAus])
async def papierkorb(benutzer=Depends(aktueller_benutzer), speicher=Depends(hole_speicher)):
    return [KnotenAus.model_validate(k) for k in await speicher.papierkorb(benutzer["id"])]


@router.post("/ordner", response_model=KnotenAus)
async def ordner_anlegen(eingabe: OrdnerEingabe, benutzer=Depends(aktueller_benutzer),
                         speicher=Depends(hole_speicher)):
    if eingabe.parent_id and not await speicher.knoten_des_nutzers(benutzer["id"], eingabe.parent_id):
        raise HTTPException(status_code=404, detail="Zielordner nicht gefunden")
    knoten = await speicher.ordner_anlegen(benutzer["id"], eingabe.parent_id, eingabe.name)
    return KnotenAus.model_validate(knoten)


@router.post("/upload", response_model=KnotenAus)
async def hochladen(datei: UploadFile, parent_id: UUID | None = Form(default=None),
                    benutzer=Depends(aktueller_benutzer), speicher=Depends(hole_speicher),
                    suche=Depends(hole_suche)):
    if parent_id and not await speicher.knoten_des_nutzers(benutzer["id"], parent_id):
        raise HTTPException(status_code=404, detail="Zielordner nicht gefunden")
    daten = await datei.read()
    name = datei.filename or "datei"
    knoten = await speicher.datei_hochladen(benutzer["id"], parent_id, name, daten)
    await suche.indexieren(benutzer["id"], knoten["id"], name, daten)
    return KnotenAus.model_validate(knoten)


@router.get("/{knoten_id}/inhalt")
async def herunterladen(knoten_id: UUID, benutzer=Depends(aktueller_benutzer),
                        speicher=Depends(hole_speicher)):
    knoten = await speicher.knoten_des_nutzers(benutzer["id"], knoten_id)
    if not knoten or knoten["typ"] != "datei" or knoten["geloescht"]:
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")
    daten = await speicher.datei_lesen(benutzer["id"], knoten_id)
    return Response(
        content=daten,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{knoten["name"]}"',
            "ETag": knoten["etag"] or "",
        },
    )


@router.get("/{knoten_id}/versionen", response_model=list[VersionAus])
async def versionen(knoten_id: UUID, benutzer=Depends(aktueller_benutzer),
                    speicher=Depends(hole_speicher)):
    liste = await speicher.versionen(benutzer["id"], knoten_id)
    if liste is None:
        raise HTTPException(status_code=404, detail="Nicht gefunden")
    return [VersionAus.model_validate(v) for v in liste]


@router.patch("/{knoten_id}/name", response_model=KnotenAus)
async def umbenennen(knoten_id: UUID, eingabe: UmbenennenEingabe,
                     benutzer=Depends(aktueller_benutzer), speicher=Depends(hole_speicher)):
    if not await speicher.knoten_des_nutzers(benutzer["id"], knoten_id):
        raise HTTPException(status_code=404, detail="Nicht gefunden")
    return KnotenAus.model_validate(await speicher.umbenennen(benutzer["id"], knoten_id, eingabe.name))


@router.patch("/{knoten_id}/ort", response_model=KnotenAus)
async def verschieben(knoten_id: UUID, eingabe: VerschiebenEingabe,
                      benutzer=Depends(aktueller_benutzer), speicher=Depends(hole_speicher)):
    if not await speicher.knoten_des_nutzers(benutzer["id"], knoten_id):
        raise HTTPException(status_code=404, detail="Nicht gefunden")
    if eingabe.parent_id and not await speicher.knoten_des_nutzers(benutzer["id"], eingabe.parent_id):
        raise HTTPException(status_code=404, detail="Zielordner nicht gefunden")
    return KnotenAus.model_validate(
        await speicher.verschieben(benutzer["id"], knoten_id, eingabe.parent_id)
    )


@router.delete("/{knoten_id}", status_code=204)
async def loeschen(knoten_id: UUID, benutzer=Depends(aktueller_benutzer),
                   speicher=Depends(hole_speicher)):
    if not await speicher.knoten_des_nutzers(benutzer["id"], knoten_id):
        raise HTTPException(status_code=404, detail="Nicht gefunden")
    await speicher.loeschen(benutzer["id"], knoten_id)


@router.post("/{knoten_id}/wiederherstellen", response_model=KnotenAus)
async def wiederherstellen(knoten_id: UUID, benutzer=Depends(aktueller_benutzer),
                           speicher=Depends(hole_speicher)):
    knoten = await speicher.wiederherstellen(benutzer["id"], knoten_id)
    if not knoten:
        raise HTTPException(status_code=404, detail="Nicht gefunden")
    return KnotenAus.model_validate(knoten)

"""Datei-Router: Browsen, Upload, Download, Umbenennen, Verschieben, Papierkorb,
Versionen. Jede Route prueft die Eigentuemerschaft des Knotens (Isolation).
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from fastapi.responses import Response
from psycopg.errors import UniqueViolation

from app.abhaengig import aktueller_benutzer, hole_speicher, hole_suche
from app.config import EINSTELLUNGEN
from module.speicher.modelle import (
    ExternEintragAus,
    KnotenAus,
    OrdnerEingabe,
    SpeicherStatusAus,
    UmbenennenEingabe,
    VerschiebenEingabe,
    VersionAus,
)

router = APIRouter(prefix="/api/v1/dateien", tags=["dateien"])


@router.get("/speicher-status", response_model=SpeicherStatusAus)
async def speicher_status(benutzer=Depends(aktueller_benutzer), speicher=Depends(hole_speicher)):
    s = await speicher.speicher_status(benutzer["id"])
    return SpeicherStatusAus(
        benutzt=s["benutzt"], quota=s["quota"], gesamt=s.get("gesamt"), frei=s.get("frei")
    )


@router.get("", response_model=list[KnotenAus])
async def auflisten(parent_id: UUID | None = None, benutzer=Depends(aktueller_benutzer),
                    speicher=Depends(hole_speicher)):
    if parent_id and not await speicher.knoten_des_nutzers(benutzer["id"], parent_id):
        raise HTTPException(status_code=404, detail="Ordner nicht gefunden")
    return [KnotenAus.model_validate(k) for k in await speicher.kinder(benutzer["id"], parent_id)]


@router.get("/papierkorb", response_model=list[KnotenAus])
async def papierkorb(benutzer=Depends(aktueller_benutzer), speicher=Depends(hole_speicher)):
    return [KnotenAus.model_validate(k) for k in await speicher.papierkorb(benutzer["id"])]


@router.delete("/papierkorb", status_code=204)
async def papierkorb_leeren(benutzer=Depends(aktueller_benutzer), speicher=Depends(hole_speicher)):
    await speicher.papierkorb_leeren(benutzer["id"])


@router.get("/extern/{knoten_id}", response_model=list[ExternEintragAus])
async def extern_auflisten(knoten_id: UUID, unterpfad: str = "",
                           benutzer=Depends(aktueller_benutzer), speicher=Depends(hole_speicher)):
    try:
        eintraege = await speicher.externe_kinder(benutzer["id"], knoten_id, unterpfad)
    except (PermissionError, FileNotFoundError, NotADirectoryError):
        raise HTTPException(status_code=404, detail="Nicht gefunden")
    if eintraege is None:
        raise HTTPException(status_code=404, detail="Keine externe Quelle")
    return [
        ExternEintragAus(name=e.name, ist_ordner=e.ist_ordner, groesse=e.groesse)
        for e in eintraege
    ]


@router.get("/extern/{knoten_id}/inhalt")
async def extern_inhalt(knoten_id: UUID, unterpfad: str,
                        benutzer=Depends(aktueller_benutzer), speicher=Depends(hole_speicher)):
    try:
        daten = await speicher.externe_datei_lesen(benutzer["id"], knoten_id, unterpfad)
    except (PermissionError, FileNotFoundError, IsADirectoryError):
        raise HTTPException(status_code=404, detail="Nicht gefunden")
    if daten is None:
        raise HTTPException(status_code=404, detail="Keine externe Quelle")
    name = unterpfad.rstrip("/").rsplit("/", 1)[-1] or "datei"
    return Response(
        content=daten,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@router.post("/ordner", response_model=KnotenAus)
async def ordner_anlegen(eingabe: OrdnerEingabe, benutzer=Depends(aktueller_benutzer),
                         speicher=Depends(hole_speicher)):
    if eingabe.parent_id and not await speicher.knoten_des_nutzers(benutzer["id"], eingabe.parent_id):
        raise HTTPException(status_code=404, detail="Zielordner nicht gefunden")
    try:
        knoten = await speicher.ordner_anlegen(benutzer["id"], eingabe.parent_id, eingabe.name)
    except UniqueViolation:
        raise HTTPException(status_code=409, detail="Name bereits vergeben")
    return KnotenAus.model_validate(knoten)


@router.post("/upload", response_model=KnotenAus)
async def hochladen(datei: UploadFile, parent_id: UUID | None = Form(default=None),
                    benutzer=Depends(aktueller_benutzer), speicher=Depends(hole_speicher),
                    suche=Depends(hole_suche)):
    if parent_id and not await speicher.knoten_des_nutzers(benutzer["id"], parent_id):
        raise HTTPException(status_code=404, detail="Zielordner nicht gefunden")
    # In Stuecken lesen und harte Obergrenze durchsetzen (Speicher-Schutz).
    stuecke, gesamt = [], 0
    while True:
        stueck = await datei.read(1024 * 1024)
        if not stueck:
            break
        gesamt += len(stueck)
        if gesamt > EINSTELLUNGEN.max_upload:
            raise HTTPException(status_code=413, detail="Datei zu gross")
        stuecke.append(stueck)
    daten = b"".join(stuecke)
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
    try:
        knoten = await speicher.umbenennen(benutzer["id"], knoten_id, eingabe.name)
    except UniqueViolation:
        raise HTTPException(status_code=409, detail="Name bereits vergeben")
    return KnotenAus.model_validate(knoten)


@router.patch("/{knoten_id}/ort", response_model=KnotenAus)
async def verschieben(knoten_id: UUID, eingabe: VerschiebenEingabe,
                      benutzer=Depends(aktueller_benutzer), speicher=Depends(hole_speicher)):
    if not await speicher.knoten_des_nutzers(benutzer["id"], knoten_id):
        raise HTTPException(status_code=404, detail="Nicht gefunden")
    try:
        knoten = await speicher.verschieben(benutzer["id"], knoten_id, eingabe.parent_id)
    except ValueError as f:
        raise HTTPException(status_code=409, detail=str(f))
    except UniqueViolation:
        raise HTTPException(status_code=409, detail="Name im Zielordner bereits vergeben")
    return KnotenAus.model_validate(knoten)


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

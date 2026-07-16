"""Datei-Router: Browsen, Upload, Download, Umbenennen, Verschieben, Papierkorb,
Versionen. Jede Route prueft die Eigentuemerschaft des Knotens (Isolation).
"""

import re
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response, StreamingResponse
from psycopg.errors import UniqueViolation

from app.abhaengig import (
    aktueller_benutzer,
    hole_auth,
    hole_speicher,
    hole_suche,
    hole_vorgaenge,
)
from app.config import EINSTELLUNGEN
from app.ports import DateiZuGross
from module.speicher.dienst import ArchivZuGross
from module.speicher.modelle import (
    ExternEintragAus,
    ExternOrdnerEingabe,
    FreigabeAus,
    KnotenAus,
    KontoAus,
    OrdnerEingabe,
    SpeicherStatusAus,
    TeilenEingabe,
    UmbenennenEingabe,
    VerschiebenEingabe,
    VersionAus,
    ZipEingabe,
)

router = APIRouter(prefix="/api/v1/dateien", tags=["dateien"])

_RANGE_MUSTER = re.compile(r"bytes=(\d*)-(\d*)")


def dateiname_kopf(name: str, art: str = "attachment") -> str:
    """Baut den Content-Disposition-Wert mit sauber kodiertem Dateinamen.

    Der Name wandert in einen HTTP-Kopf und darf dort weder mit Anfuehrungs-
    zeichen noch mit Zeilenumbruechen ausbrechen. Umlaute gehen nur ueber die
    RFC-5987-Form (filename*), deshalb zusaetzlich ein ASCII-Rueckfallname fuer
    aeltere Empfaenger - sonst kommt "Uebergewicht.mp4" verstuemmelt an.
    """
    sicher = name.replace('"', "'").replace("\r", " ").replace("\n", " ")
    ascii_name = sicher.encode("ascii", "replace").decode("ascii")
    return f"{art}; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(sicher, safe='')}"


def bereich_aus_kopf(kopf: str | None, gesamt: int) -> tuple[int | None, int | None]:
    """Wertet einen Range-Kopf aus und liefert (start, ende) oder (None, None),
    wenn nichts oder nichts Gueltiges verlangt wurde."""
    if not kopf or gesamt <= 0:
        return None, None
    m = _RANGE_MUSTER.search(kopf)
    if not m:
        return None, None
    roh_start, roh_ende = m.group(1), m.group(2)
    if not roh_start and not roh_ende:
        return None, None
    if not roh_start:
        # Suffix-Form "bytes=-500": die letzten 500 Bytes.
        n = int(roh_ende)
        if n <= 0:
            return None, None
        start, ende = max(0, gesamt - n), gesamt - 1
    else:
        start = int(roh_start)
        ende = min(int(roh_ende), gesamt - 1) if roh_ende else gesamt - 1
    if start > ende or start >= gesamt:
        return None, None
    return start, ende


@router.get("/speicher-status", response_model=SpeicherStatusAus)
async def speicher_status(benutzer=Depends(aktueller_benutzer), speicher=Depends(hole_speicher)):
    s = await speicher.speicher_status(benutzer["id"])
    return SpeicherStatusAus(
        benutzt=s["benutzt"],
        quota=s["quota"],
        gesamt=s.get("gesamt"),
        frei=s.get("frei"),
        ort=s.get("ort"),
        verfuegbar=s.get("verfuegbar", True),
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


@router.get("/favoriten", response_model=list[KnotenAus])
async def favoriten(benutzer=Depends(aktueller_benutzer), speicher=Depends(hole_speicher)):
    return [KnotenAus.model_validate(k) for k in await speicher.favoriten(benutzer["id"])]


@router.get("/konten", response_model=list[KontoAus])
async def konten(benutzer=Depends(aktueller_benutzer), auth=Depends(hole_auth)):
    """Konten-Liste (id+name) fuer den Teilen-Dialog - fuer jeden Angemeldeten."""
    return [KontoAus.model_validate(b) for b in await auth.liste_benutzer()]


@router.get("/geteilt", response_model=list[KnotenAus])
async def geteilt(benutzer=Depends(aktueller_benutzer), speicher=Depends(hole_speicher)):
    return [KnotenAus.model_validate(k) for k in await speicher.geteilt_mit(benutzer["id"])]


@router.get("/geteilt/{knoten_id}", response_model=list[KnotenAus])
async def geteilt_kinder(knoten_id: UUID, benutzer=Depends(aktueller_benutzer),
                         speicher=Depends(hole_speicher)):
    kinder = await speicher.geteilt_kinder(benutzer["id"], knoten_id)
    if kinder is None:
        raise HTTPException(status_code=404, detail="Nicht gefunden")
    return [KnotenAus.model_validate(k) for k in kinder]


@router.get("/geteilt/{knoten_id}/inhalt")
async def geteilt_inhalt(knoten_id: UUID, request: Request,
                         benutzer=Depends(aktueller_benutzer),
                         speicher=Depends(hole_speicher)):
    ergebnis = await speicher.geteilt_datei_kopf(benutzer["id"], knoten_id)
    if ergebnis is None:
        raise HTTPException(status_code=404, detail="Nicht gefunden")
    knoten, gesamt = ergebnis
    kopf = {
        "Content-Disposition": dateiname_kopf(knoten["name"]),
        "Accept-Ranges": "bytes",
    }
    start, ende = bereich_aus_kopf(request.headers.get("range"), gesamt)
    if start is None:
        kopf["Content-Length"] = str(gesamt)
        return StreamingResponse(
            speicher.geteilt_datei_stroemen(benutzer["id"], knoten_id),
            media_type="application/octet-stream", headers=kopf,
        )
    kopf["Content-Range"] = f"bytes {start}-{ende}/{gesamt}"
    kopf["Content-Length"] = str(ende - start + 1)
    return StreamingResponse(
        speicher.geteilt_datei_stroemen(benutzer["id"], knoten_id, start, ende - start + 1),
        status_code=206, media_type="application/octet-stream", headers=kopf,
    )


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


@router.post("/extern/{knoten_id}/upload", status_code=204)
async def extern_upload(knoten_id: UUID, datei: UploadFile, unterpfad: str = Form(default=""),
                        benutzer=Depends(aktueller_benutzer), speicher=Depends(hole_speicher)):
    # Wie beim normalen Upload: direkt streamen, nichts vollstaendig im Speicher.
    await datei.seek(0)
    try:
        ok = await speicher.externe_datei_schreiben_strom(
            benutzer["id"], knoten_id, unterpfad, datei.filename or "datei",
            datei.file, EINSTELLUNGEN.max_upload,
        )
    except DateiZuGross:
        raise HTTPException(status_code=413, detail="Datei zu gross")
    except (PermissionError, IsADirectoryError, OSError, ValueError):
        raise HTTPException(status_code=400, detail="Schreiben nicht moeglich")
    if not ok:
        raise HTTPException(status_code=404, detail="Keine externe Quelle")


@router.post("/extern/{knoten_id}/ordner", status_code=204)
async def extern_ordner(knoten_id: UUID, eingabe: ExternOrdnerEingabe,
                        benutzer=Depends(aktueller_benutzer), speicher=Depends(hole_speicher)):
    try:
        ok = await speicher.externe_ordner_anlegen(
            benutzer["id"], knoten_id, eingabe.unterpfad, eingabe.name
        )
    except (PermissionError, OSError, ValueError):
        raise HTTPException(status_code=400, detail="Anlegen nicht moeglich")
    if not ok:
        raise HTTPException(status_code=404, detail="Keine externe Quelle")


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
                    suche=Depends(hole_suche), vorgaenge=Depends(hole_vorgaenge)):
    if parent_id and not await speicher.knoten_des_nutzers(benutzer["id"], parent_id):
        raise HTTPException(status_code=404, detail="Zielordner nicht gefunden")
    # Direkt aus dem Strom auf die Platte: die Datei landet NIE vollstaendig im
    # Speicher, damit auch sehr grosse Dateien sicher ankommen. Die Obergrenze
    # wird beim Streamen durchgesetzt.
    name = datei.filename or "datei"
    await datei.seek(0)
    try:
        knoten, blob_hash, groesse = await speicher.datei_hochladen_strom(
            benutzer["id"], parent_id, name, datei.file, EINSTELLUNGEN.max_upload
        )
    except DateiZuGross:
        raise HTTPException(status_code=413, detail="Datei zu gross")

    # Indizierung laeuft als Hintergrund-Vorgang, damit der Upload nicht darauf
    # wartet und ein Index-Fehler den Upload nicht scheitern laesst. Der Inhalt
    # wird NUR nachgelesen, wenn die Extraktion ihn auch nutzt - sonst wuerde eine
    # grosse Datei allein fuer den Index im Speicher gehalten.
    async def _indizieren(_vorgang):
        inhalt = b""
        if suche.braucht_inhalt(name, groesse):
            inhalt = await speicher.blob_get(str(benutzer["id"]), blob_hash, groesse)
        await suche.indexieren(benutzer["id"], knoten["id"], name, inhalt)

    vorgaenge.starte(benutzer["id"], "indizierung", f"{name} indizieren", _indizieren)
    return KnotenAus.model_validate(knoten)


@router.post("/zip")
async def als_zip(eingabe: ZipEingabe, benutzer=Depends(aktueller_benutzer),
                  speicher=Depends(hole_speicher)):
    try:
        daten = await speicher.als_zip(benutzer["id"], [str(i) for i in eingabe.ids])
    except ArchivZuGross:
        raise HTTPException(status_code=413, detail="Auswahl zu gross fuer ein ZIP")
    if daten is None:
        raise HTTPException(status_code=404, detail="Nichts zum Packen")
    return Response(
        content=daten,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="kellerwolke.zip"'},
    )


@router.get("/{knoten_id}/inhalt")
async def herunterladen(knoten_id: UUID, request: Request,
                        benutzer=Depends(aktueller_benutzer),
                        speicher=Depends(hole_speicher)):
    knoten = await speicher.knoten_des_nutzers(benutzer["id"], knoten_id)
    if not knoten or knoten["typ"] != "datei" or knoten["geloescht"]:
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")
    gesamt = await speicher.datei_groesse(benutzer["id"], knoten_id)
    kopf = {
        "Content-Disposition": dateiname_kopf(knoten["name"]),
        "ETag": knoten["etag"] or "",
        # Range melden: so kann ein abgebrochener Download fortgesetzt werden,
        # statt bei einer grossen Datei wieder bei 0 zu beginnen.
        "Accept-Ranges": "bytes",
    }

    start, ende = bereich_aus_kopf(request.headers.get("range"), gesamt)
    if start is None:
        # Ganze Datei - aber STUECKWEISE, nie als Vollpuffer im Speicher.
        kopf["Content-Length"] = str(gesamt)
        return StreamingResponse(
            speicher.datei_stroemen(benutzer["id"], knoten_id),
            media_type="application/octet-stream", headers=kopf,
        )
    kopf["Content-Range"] = f"bytes {start}-{ende}/{gesamt}"
    kopf["Content-Length"] = str(ende - start + 1)
    return StreamingResponse(
        speicher.datei_stroemen(benutzer["id"], knoten_id, start, ende - start + 1),
        status_code=206, media_type="application/octet-stream", headers=kopf,
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


@router.delete("/{knoten_id}/endgueltig", status_code=204)
async def endgueltig_loeschen(knoten_id: UUID, benutzer=Depends(aktueller_benutzer),
                              speicher=Depends(hole_speicher)):
    # Nur fuer eigene, bereits im Papierkorb liegende Knoten; sonst 404.
    if not await speicher.knoten_endgueltig_loeschen(benutzer["id"], knoten_id):
        raise HTTPException(status_code=404, detail="Nicht gefunden")


@router.post("/{knoten_id}/favorit", status_code=204)
async def favorit_an(knoten_id: UUID, benutzer=Depends(aktueller_benutzer),
                     speicher=Depends(hole_speicher)):
    if not await speicher.knoten_des_nutzers(benutzer["id"], knoten_id):
        raise HTTPException(status_code=404, detail="Nicht gefunden")
    await speicher.favorit_setzen(benutzer["id"], knoten_id, True)


@router.delete("/{knoten_id}/favorit", status_code=204)
async def favorit_aus(knoten_id: UUID, benutzer=Depends(aktueller_benutzer),
                      speicher=Depends(hole_speicher)):
    await speicher.favorit_setzen(benutzer["id"], knoten_id, False)


@router.get("/{knoten_id}/freigaben", response_model=list[FreigabeAus])
async def freigaben(knoten_id: UUID, benutzer=Depends(aktueller_benutzer),
                    speicher=Depends(hole_speicher)):
    liste = await speicher.freigaben(benutzer["id"], knoten_id)
    if liste is None:
        raise HTTPException(status_code=404, detail="Nicht gefunden")
    return [FreigabeAus.model_validate(f) for f in liste]


@router.post("/{knoten_id}/teilen", status_code=204)
async def teilen(knoten_id: UUID, eingabe: TeilenEingabe, benutzer=Depends(aktueller_benutzer),
                 speicher=Depends(hole_speicher)):
    rechte = eingabe.rechte if eingabe.rechte in ("lesen", "schreiben") else "lesen"
    if not await speicher.teilen(benutzer["id"], knoten_id, eingabe.ziel_benutzer_id, rechte):
        raise HTTPException(status_code=404, detail="Nicht gefunden")


@router.delete("/{knoten_id}/teilen/{ziel_id}", status_code=204)
async def teilen_entfernen(knoten_id: UUID, ziel_id: UUID, benutzer=Depends(aktueller_benutzer),
                           speicher=Depends(hole_speicher)):
    if not await speicher.teilen_entfernen(benutzer["id"], knoten_id, ziel_id):
        raise HTTPException(status_code=404, detail="Nicht gefunden")


@router.post("/{knoten_id}/wiederherstellen", response_model=KnotenAus)
async def wiederherstellen(knoten_id: UUID, benutzer=Depends(aktueller_benutzer),
                           speicher=Depends(hole_speicher)):
    knoten = await speicher.wiederherstellen(benutzer["id"], knoten_id)
    if not knoten:
        raise HTTPException(status_code=404, detail="Nicht gefunden")
    return KnotenAus.model_validate(knoten)

"""Datei-Router: Browsen, Upload, Download, Umbenennen, Verschieben, Papierkorb,
Versionen. Jede Route prueft die Eigentuemerschaft des Knotens (Isolation).
"""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from psycopg.errors import UniqueViolation

from app.abhaengig import (
    aktueller_benutzer,
    hole_auth,
    hole_speicher,
    hole_suche,
    hole_vorgaenge,
)
from app.auslieferung import dateiname_kopf, inhalt_antwort
from app.config import EINSTELLUNGEN
from app.inhaltstyp import inhaltstyp_aus_name
from app.ports import DateiZuGross
from module.speicher.dienst import ArchivZuGross, NameBelegt, ZielUngueltig
from module.speicher.modelle import (
    ExternEintragAus,
    FreigabeAus,
    KnotenAus,
    KontoAus,
    OrdnerEingabe,
    PfadteilAus,
    SpeicherStatusAus,
    TeilenEingabe,
    UmbenennenEingabe,
    VerschiebenEingabe,
    VersionAus,
    ZipEingabe,
)

router = APIRouter(prefix="/api/v1/dateien", tags=["dateien"])

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
    if parent_id and not await speicher.lebender_knoten(benutzer["id"], parent_id):
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
async def geteilt_inhalt(knoten_id: UUID, request: Request, benutzer=Depends(aktueller_benutzer),
                         speicher=Depends(hole_speicher)):
    return await _datei_ausliefern(request, speicher, await speicher.lesbare_datei(benutzer["id"], knoten_id))


async def _datei_ausliefern(request: Request, speicher, stand):
    """Download einer lesbaren Datei (eigene oder geteilte), ganz oder als Bereich."""
    if stand is None:
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")
    return inhalt_antwort(
        request, gesamt=stand.groesse, strom=lambda start, laenge: speicher.stand_stroemen(stand, start, laenge),
        inhaltstyp=await speicher.inhaltstyp(stand.knoten), dateiname=stand.knoten["name"], etag=stand.etag,
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
        ExternEintragAus(name=e.name, ist_ordner=e.ist_ordner, groesse=e.groesse,
                         geaendert_am=datetime.fromtimestamp(e.geaendert, timezone.utc) if e.geaendert else None)
        for e in eintraege
    ]


@router.get("/extern/{knoten_id}/inhalt")
async def extern_inhalt(knoten_id: UUID, unterpfad: str, request: Request,
                        benutzer=Depends(aktueller_benutzer), speicher=Depends(hole_speicher)):
    """Externe Quellen sind nur lesbar; der Inhalt strömt direkt von der Platte."""
    try:
        gefunden = await speicher.externe_datei(benutzer["id"], knoten_id, unterpfad)
    except (PermissionError, FileNotFoundError, IsADirectoryError, NotADirectoryError):
        raise HTTPException(status_code=404, detail="Nicht gefunden")
    if gefunden is None:
        raise HTTPException(status_code=404, detail="Keine externe Quelle")
    quelle, eintrag = gefunden
    return inhalt_antwort(
        request, gesamt=eintrag.groesse, inhaltstyp=inhaltstyp_aus_name(eintrag.name), dateiname=eintrag.name,
        strom=lambda start, laenge: speicher.extern_stroemen(quelle, unterpfad, start, laenge, gesamt=eintrag.groesse),
    )


@router.post("/ordner", response_model=KnotenAus)
async def ordner_anlegen(eingabe: OrdnerEingabe, benutzer=Depends(aktueller_benutzer),
                         speicher=Depends(hole_speicher)):
    try:
        knoten = await speicher.ordner_anlegen(benutzer["id"], eingabe.parent_id, eingabe.name)
    except ZielUngueltig:
        raise HTTPException(status_code=404, detail="Zielordner nicht gefunden")
    except UniqueViolation:
        raise HTTPException(status_code=409, detail="Name bereits vergeben")
    return KnotenAus.model_validate(knoten)


@router.post("/upload", response_model=KnotenAus)
async def hochladen(datei: UploadFile, parent_id: UUID | None = Form(default=None),
                    benutzer=Depends(aktueller_benutzer), speicher=Depends(hole_speicher),
                    suche=Depends(hole_suche), vorgaenge=Depends(hole_vorgaenge)):
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
        raise HTTPException(status_code=413, detail="Datei zu groß")
    except ZielUngueltig:
        raise HTTPException(status_code=404, detail="Zielordner nicht gefunden")
    except NameBelegt as f:
        raise HTTPException(status_code=409, detail=str(f))

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
    ids = [str(i) for i in eingabe.ids]
    # Der Plan laeuft nur ueber Metadaten: so stehen "nichts zu packen" und "zu
    # gross" fest, BEVOR das Streamen beginnt - danach liesse sich kein sauberer
    # Fehlercode mehr senden, weil die Antwort schon laeuft.
    try:
        plan = await speicher.zip_plan(benutzer["id"], ids)
    except ArchivZuGross:
        raise HTTPException(status_code=413, detail="Auswahl zu gross fuer ein ZIP")
    if not plan:
        raise HTTPException(status_code=404, detail="Nichts zum Packen")
    return StreamingResponse(
        speicher.zip_stroemen(benutzer["id"], ids),
        media_type="application/zip",
        headers={"Content-Disposition": dateiname_kopf("kellerwolke.zip")},
    )


@router.get("/{knoten_id}/inhalt")
async def herunterladen(knoten_id: UUID, request: Request, benutzer=Depends(aktueller_benutzer),
                        speicher=Depends(hole_speicher)):
    return await _datei_ausliefern(request, speicher, await speicher.eigene_datei(benutzer["id"], knoten_id))


@router.get("/{knoten_id}/pfad", response_model=list[PfadteilAus])
async def pfad(knoten_id: UUID, benutzer=Depends(aktueller_benutzer), speicher=Depends(hole_speicher)):
    """Ordnerkette über einem eigenen Knoten (ohne "Meine Dateien" und ohne den Knoten selbst)."""
    kette = await speicher.ahnen(benutzer["id"], knoten_id)
    if kette is None:
        raise HTTPException(status_code=404, detail="Nicht gefunden")
    return kette


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
    try:
        knoten = await speicher.umbenennen(benutzer["id"], knoten_id, eingabe.name)
    except ZielUngueltig:
        raise HTTPException(status_code=404, detail="Nicht gefunden")
    except UniqueViolation:
        raise HTTPException(status_code=409, detail="Name bereits vergeben")
    return KnotenAus.model_validate(knoten)


@router.patch("/{knoten_id}/ort", response_model=KnotenAus)
async def verschieben(knoten_id: UUID, eingabe: VerschiebenEingabe,
                      benutzer=Depends(aktueller_benutzer), speicher=Depends(hole_speicher)):
    if not await speicher.lebender_knoten(benutzer["id"], knoten_id):
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
    if not await speicher.lebender_knoten(benutzer["id"], knoten_id):
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
    if not await speicher.lebender_knoten(benutzer["id"], knoten_id):
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

"""Inhalts-Router für den Browser: Herunterladen, ZIP, Vorschau, Vollbild und Wiedergabe für alles, was das Konto
lesen darf (eigene und geteilte Dateien).

<img>, <audio>, <video> und ein gewöhnlicher Download-Link können keine Köpfe setzen. Statt des Sitzungsschlüssels
in der Adresse gibt es deshalb einen Lesezugang: ein Cookie nur für diesen Pfad, für Skripte unlesbar, nicht
seitenübergreifend gesendet und an die Sitzung gebunden (Abmelden beendet ihn). Der Browser lädt damit direkt aus
dem Strom, mit Fortschritt und ohne die Datei im Speicher zu halten. Adressen tragen den Versionsstand (?v=ETag):
passt er, darf der Browser dauerhaft zwischenspeichern; nach einer neuen Version lautet die Adresse anders.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response
from fastapi.responses import FileResponse

from app.abhaengig import LESEZUGANG_COOKIE, aktueller_benutzer, hole_medien, hole_speicher, lese_benutzer
from app.auslieferung import inhalt_antwort
from app.inhaltstyp import inhaltstyp_aus_name
from module.medien.arten import UMWANDELN, VEKTOR, Medienart, endung, medienart
from module.medien.vorschau import KeinBild, KeinStandbild, Stufe
from module.speicher.api import zip_antwort

router = APIRouter(prefix="/api/v1/inhalt", tags=["inhalt"])

_PFAD = "/api/v1/inhalt"
_ZUGANG_DAUER = 30 * 24 * 3600
# Als Dokument geöffnet (neuer Tab) läuft in einer Inhaltsantwort nichts: kein Skript, keine Verbindung nach außen.
_ABGESCHOTTET = {"Content-Security-Policy": "default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'; "
                                           "media-src 'self'; sandbox"}


def _https(request: Request) -> bool:
    return request.url.scheme == "https" or request.headers.get("x-forwarded-proto", "") == "https"


@router.post("/zugang", status_code=204)
async def zugang(request: Request, response: Response, benutzer=Depends(aktueller_benutzer)):
    """Richtet den Lesezugang dieser Sitzung ein (beim Start der Oberfläche)."""
    response.set_cookie(LESEZUGANG_COOKIE, request.headers["x-kellerwolke-sitzung"], max_age=_ZUGANG_DAUER, path=_PFAD,
                        httponly=True, samesite="strict", secure=_https(request))


@router.delete("/zugang", status_code=204)
async def zugang_beenden(request: Request, response: Response):
    response.delete_cookie(LESEZUGANG_COOKIE, path=_PFAD, httponly=True, samesite="strict", secure=_https(request))


def _cache(v: str | None, stand) -> str:
    return "private, max-age=31536000, immutable" if v and v == stand.etag else "private, no-cache"


async def _medium(speicher, benutzer, knoten_id, *arten: Medienart):
    stand = await speicher.lesbare_datei(benutzer["id"], knoten_id)
    if stand is None or medienart(stand.knoten["name"]) not in arten:
        raise HTTPException(status_code=404, detail="Medium nicht gefunden")
    return stand


async def _original(request: Request, speicher, stand, v: str | None) -> Response:
    return inhalt_antwort(
        request, gesamt=stand.groesse, strom=lambda start, laenge: speicher.stand_stroemen(stand, start, laenge),
        inhaltstyp=await speicher.inhaltstyp(stand.knoten), dateiname=stand.knoten["name"], art="inline",
        etag=stand.etag, cache=_cache(v, stand), zusatz=_ABGESCHOTTET,
    )


def _datei(pfad, typ: str, v: str | None, stand) -> FileResponse:
    return FileResponse(pfad, media_type=typ, headers={"Cache-Control": _cache(v, stand), **_ABGESCHOTTET})


@router.get("/vorschau/{knoten_id}")
async def vorschau(knoten_id: UUID, request: Request, stufe: Stufe = Stufe.gross, v: str | None = None,
                   benutzer=Depends(lese_benutzer), speicher=Depends(hole_speicher), medien=Depends(hole_medien)):
    stand = await _medium(speicher, benutzer, knoten_id, "bild", "video")
    if endung(stand.knoten["name"]) in VEKTOR:
        return await _original(request, speicher, stand, v)
    try:
        return _datei(await medien.vorschau(stand, stufe), "image/webp", v, stand)
    except KeinStandbild:
        raise HTTPException(status_code=404, detail="Kein Standbild für dieses Video")
    except KeinBild:
        raise HTTPException(status_code=415, detail="Bild nicht darstellbar")


@router.get("/voll/{knoten_id}")
async def voll(knoten_id: UUID, request: Request, v: str | None = None, benutzer=Depends(lese_benutzer),
               speicher=Depends(hole_speicher), medien=Depends(hole_medien)):
    """Das Bild in voller Größe: das Original, nur HEIC einmal als JPEG."""
    stand = await _medium(speicher, benutzer, knoten_id, "bild")
    if endung(stand.knoten["name"]) not in UMWANDELN:
        return await _original(request, speicher, stand, v)
    try:
        return _datei(await medien.voll_umgewandelt(stand), "image/jpeg", v, stand)
    except KeinBild:
        raise HTTPException(status_code=415, detail="Bild nicht darstellbar")


@router.get("/strom/{knoten_id}")
async def strom(knoten_id: UUID, request: Request, v: str | None = None, benutzer=Depends(lese_benutzer),
                speicher=Depends(hole_speicher)):
    """Audio und Video, mit Bereichen für Spulen und Fortsetzen."""
    return await _original(request, speicher, await _medium(speicher, benutzer, knoten_id, "audio", "video"), v)


@router.get("/datei/{knoten_id}")
async def datei(knoten_id: UUID, request: Request, benutzer=Depends(lese_benutzer), speicher=Depends(hole_speicher)):
    """Herunterladen einer lesbaren Datei (eigene oder geteilte), auch fortsetzbar."""
    stand = await speicher.lesbare_datei(benutzer["id"], knoten_id)
    if stand is None:
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")
    return inhalt_antwort(
        request, gesamt=stand.groesse, strom=lambda start, laenge: speicher.stand_stroemen(stand, start, laenge),
        inhaltstyp=await speicher.inhaltstyp(stand.knoten), dateiname=stand.knoten["name"], etag=stand.etag,
        zusatz=_ABGESCHOTTET,
    )


@router.post("/zip")
async def zip_herunterladen(ids: list[UUID] = Form(), name: str = Form("kellerwolke.zip", max_length=255),
                            benutzer=Depends(lese_benutzer), speicher=Depends(hole_speicher)):
    """Eigene Dateien und Ordner als ZIP, als Formular abgeschickt (lange Auswahl passt in keine Adresse)."""
    return await zip_antwort(speicher, benutzer["id"], ids, name)


@router.get("/extern/{knoten_id}")
async def extern(knoten_id: UUID, unterpfad: str, request: Request, benutzer=Depends(lese_benutzer),
                 speicher=Depends(hole_speicher)):
    """Herunterladen aus einer eigenen externen Quelle (nur lesbar), direkt von der Platte."""
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
        zusatz=_ABGESCHOTTET,
    )


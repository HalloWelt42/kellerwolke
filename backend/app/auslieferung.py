"""Auslieferung von Dateiinhalten über HTTP, eine Stelle für alle Wege (eigene und geteilte Dateien, Apps, Medien,
WebDAV, externe Quellen).

Ganz oder als Bereich (Range nach RFC 9110: auch die Suffix-Form, unerfüllbar gibt 416), mit Validierung über ETag
(If-None-Match gibt 304, If-Range liefert bei geändertem Stand die ganze Datei statt eines falschen Ausschnitts).
Der Inhalt geht immer stückweise hinaus: der Speicherbedarf hängt nie an der Dateigröße.
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Literal
from urllib.parse import quote

from starlette.requests import Request
from starlette.responses import Response, StreamingResponse

_EIN_BEREICH = re.compile(r"^\s*bytes\s*=\s*(\d*)\s*-\s*(\d*)\s*$")

# Liefert den Inhalt ab start, laenge Bytes (-1 bis zum Ende), stückweise.
Strom = Callable[[int, int], AsyncIterator[bytes]]


@dataclass(frozen=True)
class Bereich:
    start: int
    ende: int  # einschließlich

    @property
    def laenge(self) -> int:
        return self.ende - self.start + 1


class NichtErfuellbar(Exception):
    """Der verlangte Bereich liegt ganz hinter dem Ende der Datei (416)."""


def bereich_aus_kopf(kopf: str | None, gesamt: int) -> Bereich | None:
    """Wertet einen Range-Kopf aus. None heißt: ganze Datei (kein, ein ungültiger oder ein Mehrfach-Bereich, den wir
    nicht zerlegen). Wirft NichtErfuellbar, wenn der Bereich hinter dem Ende beginnt."""
    if not kopf:
        return None
    m = _EIN_BEREICH.match(kopf)
    if not m or not (m.group(1) or m.group(2)):
        return None
    roh_start, roh_ende = m.group(1), m.group(2)
    if not roh_start:
        n = int(roh_ende)  # Suffix-Form "bytes=-500": die letzten 500 Bytes
        if n == 0 or gesamt == 0:
            raise NichtErfuellbar()
        return Bereich(max(0, gesamt - n), gesamt - 1)
    start = int(roh_start)
    if roh_ende and int(roh_ende) < start:
        return None
    if start >= gesamt:
        raise NichtErfuellbar()
    ende = min(int(roh_ende), gesamt - 1) if roh_ende else gesamt - 1
    return Bereich(start, ende)


def dateiname_kopf(name: str, art: Literal["attachment", "inline"] = "attachment") -> str:
    """Content-Disposition mit sauber kodiertem Namen: kein Ausbrechen über Anführungszeichen oder Zeilenumbrüche,
    Umlaute und Sonderzeichen über filename* (RFC 5987), dazu ein ASCII-Rückfallname."""
    sicher = name.replace('"', "'").replace("\r", " ").replace("\n", " ")
    ascii_name = sicher.encode("ascii", "replace").decode("ascii")
    return f"{art}; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(sicher, safe='')}"


def etag_wert(etag: str) -> str:
    return f'"{etag}"'


def _passt(liste: str, etag: str) -> bool:
    werte = [w.strip().removeprefix("W/").strip('"') for w in liste.split(",")]
    return "*" in werte or etag in werte


def inhalt_antwort(request: Request, *, gesamt: int, strom: Strom, inhaltstyp: str, dateiname: str | None = None,
                   art: Literal["attachment", "inline"] = "attachment", etag: str | None = None,
                   cache: str = "private, no-cache", zusatz: dict[str, str] | None = None,
                   mit_koerper: bool = True) -> Response:
    kopf = {"Accept-Ranges": "bytes", "Cache-Control": cache, "X-Content-Type-Options": "nosniff", **(zusatz or {})}
    if dateiname is not None:
        kopf["Content-Disposition"] = dateiname_kopf(dateiname, art)
    if etag:
        kopf["ETag"] = etag_wert(etag)
        wenn_nicht = request.headers.get("if-none-match")
        if wenn_nicht and _passt(wenn_nicht, etag):
            return Response(status_code=304, headers=kopf)

    bereich = None
    wenn_bereich = request.headers.get("if-range")
    if not wenn_bereich or (etag and wenn_bereich.strip().strip('"') == etag):
        try:
            bereich = bereich_aus_kopf(request.headers.get("range"), gesamt)
        except NichtErfuellbar:
            return Response(status_code=416, headers={**kopf, "Content-Range": f"bytes */{gesamt}"})

    if bereich is None:
        kopf["Content-Length"] = str(gesamt)
        status, start, laenge = 200, 0, -1
    else:
        kopf["Content-Length"] = str(bereich.laenge)
        kopf["Content-Range"] = f"bytes {bereich.start}-{bereich.ende}/{gesamt}"
        status, start, laenge = 206, bereich.start, bereich.laenge
    if not mit_koerper:
        return Response(status_code=status, headers=kopf, media_type=inhaltstyp)
    return StreamingResponse(strom(start, laenge), status_code=status, media_type=inhaltstyp, headers=kopf)

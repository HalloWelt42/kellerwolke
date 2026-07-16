"""Medien-Plugin: register(kontext) baut den Router. Bild-Thumbnail/-Vollbild,
Audio-Streaming mit HTTP-Range (fuers Spulen) und die baumweite Medienliste.
Auth ueber Query-Token (?t=), weil <img>/<audio> keine Header setzen koennen.
"""

import re

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response, StreamingResponse

from app.plugin_api import PluginBeschreibung, PluginKontext

from .dienst import MedienDienst

_RANGE = re.compile(r"bytes=(\d*)-(\d*)")


def register(kontext: PluginKontext) -> PluginBeschreibung:
    dienst = MedienDienst(kontext)
    router = APIRouter(prefix="/api/v1/plugins/medien", tags=["medien"])

    async def benutzer(request: Request):
        t = request.query_params.get("t") or request.headers.get("x-kellerwolke-sitzung", "")
        b = await kontext.auth.sitzung_pruefen(t)
        if not b:
            raise HTTPException(status_code=401, detail="Anmeldung erforderlich")
        return b

    @router.get("/thumb/{knoten_id}")
    async def thumb(knoten_id: str, request: Request, kante: int = Query(320, ge=32, le=2000)):
        b = await benutzer(request)
        try:
            daten, typ = await dienst.thumb(b["id"], knoten_id, kante)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Bild nicht gefunden")
        except Exception:  # noqa: BLE001
            raise HTTPException(status_code=415, detail="Bild nicht darstellbar")
        return Response(content=daten, media_type=typ,
                        headers={"Cache-Control": "private, max-age=86400"})

    @router.get("/inline/{knoten_id}")
    async def inline(knoten_id: str, request: Request):
        b = await benutzer(request)
        try:
            daten, typ = await dienst.inline(b["id"], knoten_id)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Bild nicht gefunden")
        except Exception:  # noqa: BLE001
            raise HTTPException(status_code=415, detail="Bild nicht darstellbar")
        return Response(content=daten, media_type=typ, headers={"Content-Disposition": "inline"})

    # Ohne Range wuerde der Browser die ganze Datei am Stueck ziehen. Wir liefern
    # deshalb auch dann nur ein erstes Fenster und melden per Accept-Ranges, dass
    # er sich den Rest bereichsweise holen kann.
    _FENSTER = 2 * 1024 * 1024

    @router.get("/stream/{knoten_id}")
    async def stream(knoten_id: str, request: Request):
        b = await benutzer(request)
        try:
            gesamt, typ = await dienst.strom_kopf(b["id"], knoten_id)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Medium nicht gefunden")
        except Exception:  # noqa: BLE001
            raise HTTPException(status_code=415, detail="Medium nicht abspielbar")
        if gesamt <= 0:
            raise HTTPException(status_code=415, detail="Medium ist leer")

        bereich = request.headers.get("range")
        m = _RANGE.match(bereich) if bereich else None
        start = int(m.group(1)) if m and m.group(1) else 0
        if m and m.group(2):
            ende = min(int(m.group(2)), gesamt - 1)
        else:
            # Offenes Ende: nur ein Fenster ausliefern, nicht den ganzen Rest.
            ende = min(start + _FENSTER - 1, gesamt - 1)
        start = max(0, min(start, gesamt - 1))
        if ende < start:
            ende = start
        # Stueckweise ausliefern: auch eine grosse Range (der Browser darf sie
        # verlangen) landet nie am Stueck im Speicher.
        return StreamingResponse(
            dienst.strom_stroemen(b["id"], knoten_id, start, ende - start + 1),
            status_code=206, media_type=typ, headers={
                "Content-Range": f"bytes {start}-{ende}/{gesamt}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(ende - start + 1),
                "Cache-Control": "private, max-age=86400",
            },
        )

    @router.get("/alle")
    async def alle(request: Request):
        b = await benutzer(request)
        return await dienst.alle_medien(b["id"])

    return PluginBeschreibung(router=router)

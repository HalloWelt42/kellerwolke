"""Galerie-Plugin: register(kontext) baut den Router. Zwei Bild-Endpunkte fuer
<img src> - serverseitige Thumbnails und browser-taugliche Vollbilder.

Auth ueber Query-Token (?t=...), weil <img>-Tags keine Header setzen koennen;
der Header x-kellerwolke-sitzung wird zusaetzlich akzeptiert. Eigentuemerpruefung
laeuft identisch zum Datei-Download ueber den SpeicherDienst.
"""

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response

from app.plugin_api import PluginBeschreibung, PluginKontext

from .dienst import GalerieDienst


def register(kontext: PluginKontext) -> PluginBeschreibung:
    dienst = GalerieDienst(kontext)
    router = APIRouter(prefix="/api/v1/plugins/galerie", tags=["galerie"])

    async def benutzer_aus_token(request: Request):
        token = request.query_params.get("t") or request.headers.get("x-kellerwolke-sitzung", "")
        benutzer = await kontext.auth.sitzung_pruefen(token)
        if not benutzer:
            raise HTTPException(status_code=401, detail="Anmeldung erforderlich")
        return benutzer

    @router.get("/thumb/{knoten_id}")
    async def thumb(knoten_id: str, request: Request, kante: int = Query(320, ge=32, le=2000)):
        benutzer = await benutzer_aus_token(request)
        try:
            daten, typ = await dienst.thumb(benutzer["id"], knoten_id, kante)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Bild nicht gefunden")
        except Exception:  # noqa: BLE001 - defektes/unlesbares Bild -> 415 statt 500
            raise HTTPException(status_code=415, detail="Bild kann nicht dargestellt werden")
        return Response(content=daten, media_type=typ,
                        headers={"Cache-Control": "private, max-age=86400"})

    @router.get("/inline/{knoten_id}")
    async def inline(knoten_id: str, request: Request):
        benutzer = await benutzer_aus_token(request)
        try:
            daten, typ = await dienst.inline(benutzer["id"], knoten_id)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Bild nicht gefunden")
        except Exception:  # noqa: BLE001
            raise HTTPException(status_code=415, detail="Bild kann nicht dargestellt werden")
        return Response(content=daten, media_type=typ, headers={"Content-Disposition": "inline"})

    return PluginBeschreibung(router=router)

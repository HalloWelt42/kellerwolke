"""WebDAV-Adapter ueber dieselbe Service-Schicht wie die REST-API.

Mountet unter /webdav und spricht ausschliesslich den SpeicherDienst an, damit
ETags und Journal konsistent bleiben. Authentifizierung per HTTP Basic (Name
oder Kuerzel + Passwort), passend fuer jeden Dateimanager mit WebDAV-Unterstuetzung.
Bewusst minimal, aber funktional: OPTIONS, PROPFIND, GET, HEAD, PUT, DELETE, MKCOL, MOVE.
"""

import base64
from datetime import datetime, timezone
from email.utils import format_datetime
from urllib.parse import quote, unquote, urlsplit
from xml.sax.saxutils import escape

from psycopg.errors import UniqueViolation
from starlette.requests import Request
from starlette.responses import Response

from app.config import EINSTELLUNGEN

BASIS = "/webdav"
_METHODEN = ["OPTIONS", "GET", "HEAD", "PUT", "DELETE", "PROPFIND", "MKCOL", "MOVE", "COPY"]


def webdav_einbinden(app) -> None:
    app.add_route(BASIS, webdav_endpoint, methods=_METHODEN)
    app.add_route(BASIS + "/{pfad:path}", webdav_endpoint, methods=_METHODEN)


async def _auth(request: Request):
    kopf = request.headers.get("authorization", "")
    if not kopf.startswith("Basic "):
        return None
    try:
        roh = base64.b64decode(kopf[6:]).decode("utf-8")
    except Exception:
        return None
    kennung, _, passwort = roh.partition(":")
    return await request.app.state.auth.pruefe_basis(kennung, passwort)


def _401() -> Response:
    return Response(status_code=401, headers={"WWW-Authenticate": 'Basic realm="Kellerwolke"'})


def _options() -> Response:
    return Response(
        status_code=200,
        headers={
            "DAV": "1",
            "Allow": "OPTIONS, GET, HEAD, PUT, DELETE, PROPFIND, MKCOL, MOVE",
            "MS-Author-Via": "DAV",
        },
    )


def _href(pfad: str, ist_ordner: bool) -> str:
    teile = [quote(t) for t in pfad.split("/") if t]
    href = BASIS + "/" + "/".join(teile)
    if ist_ordner and not href.endswith("/"):
        href += "/"
    return href


def _prop(name: str, pfad: str, ist_ordner: bool, groesse: int, geaendert, etag) -> str:
    felder = [
        f"<D:displayname>{escape(name)}</D:displayname>",
        f"<D:getlastmodified>{format_datetime(geaendert, usegmt=True)}</D:getlastmodified>",
    ]
    if ist_ordner:
        felder.append("<D:resourcetype><D:collection/></D:resourcetype>")
    else:
        felder.append("<D:resourcetype/>")
        felder.append(f"<D:getcontentlength>{groesse}</D:getcontentlength>")
        if etag:
            felder.append(f'<D:getetag>"{escape(etag)}"</D:getetag>')
    return (
        f"<D:response><D:href>{_href(pfad, ist_ordner)}</D:href>"
        f"<D:propstat><D:prop>{''.join(felder)}</D:prop>"
        f"<D:status>HTTP/1.1 200 OK</D:status></D:propstat></D:response>"
    )


async def _knoten_prop(speicher, knoten, pfad: str) -> str:
    ist_ordner = knoten["typ"] in ("ordner", "extern")
    if ist_ordner:
        groesse = 0
    else:
        # Die Listen-Abfrage (kinder) liefert die Groesse bereits per LEFT JOIN
        # mit; nur bei Einzel-Knoten ohne diese Spalte eine Abfrage nachziehen.
        vorhanden = knoten.get("groesse") if hasattr(knoten, "get") else None
        groesse = vorhanden if vorhanden is not None else await speicher.groesse(knoten)
    return _prop(knoten["name"], pfad, ist_ordner, groesse, knoten["geaendert_am"], knoten["etag"])


def _eltern_und_name(pfad: str):
    eltern, _, name = pfad.rstrip("/").rpartition("/")
    return eltern, name


def _ziel_pfad(ziel: str):
    if not ziel:
        return None
    pfad = urlsplit(ziel).path or ziel
    marke = BASIS + "/"
    if marke in pfad:
        pfad = pfad.split(marke, 1)[1]
    elif pfad.startswith(BASIS):
        pfad = pfad[len(BASIS):].lstrip("/")
    return unquote(pfad)


async def _propfind(request, benutzer, pfad) -> Response:
    speicher = request.app.state.speicher
    tiefe = request.headers.get("depth", "1")
    teile = []
    if pfad == "":
        teile.append(_prop("/", "", True, 0, datetime.now(timezone.utc), None))
        if tiefe != "0":
            for k in await speicher.kinder(benutzer["id"], None):
                teile.append(await _knoten_prop(speicher, k, k["name"]))
    else:
        knoten = await speicher.knoten_per_pfad(benutzer["id"], pfad)
        if not knoten or knoten["geloescht"]:
            return Response(status_code=404)
        basis = pfad.rstrip("/")
        teile.append(await _knoten_prop(speicher, knoten, basis))
        if knoten["typ"] in ("ordner", "extern") and tiefe != "0":
            for k in await speicher.kinder(benutzer["id"], knoten["id"]):
                teile.append(await _knoten_prop(speicher, k, basis + "/" + k["name"]))
    koerper = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<D:multistatus xmlns:D="DAV:">' + "".join(teile) + "</D:multistatus>"
    )
    return Response(content=koerper, status_code=207, media_type='application/xml; charset="utf-8"')


async def _get(request, benutzer, pfad, mit_koerper) -> Response:
    speicher = request.app.state.speicher
    knoten = await speicher.knoten_per_pfad(benutzer["id"], pfad)
    if not knoten or knoten["geloescht"] or knoten["typ"] != "datei":
        return Response(status_code=404)
    daten = await speicher.datei_lesen(benutzer["id"], knoten["id"])
    kopf = {"Content-Length": str(len(daten))}
    if knoten["etag"]:
        kopf["ETag"] = f'"{knoten["etag"]}"'
    if not mit_koerper:
        return Response(status_code=200, headers=kopf)
    return Response(content=daten, media_type="application/octet-stream", headers=kopf)


async def _put(request, benutzer, pfad) -> Response:
    speicher = request.app.state.speicher
    suche = request.app.state.suche
    eltern, name = _eltern_und_name(pfad)
    if not name:
        return Response(status_code=400)
    parent = None
    if eltern:
        elt = await speicher.knoten_per_pfad(benutzer["id"], eltern)
        if not elt or elt["typ"] != "ordner":
            return Response(status_code=409)
        parent = elt["id"]
    laenge = request.headers.get("content-length")
    if laenge and int(laenge) > EINSTELLUNGEN.max_upload:
        return Response(status_code=413)
    vorher = await speicher.knoten_per_pfad(benutzer["id"], pfad)
    existierte = bool(vorher and not vorher["geloescht"] and vorher["typ"] == "datei")
    # Body streamend lesen und die Grenze laufend pruefen (Speicher-Schutz, auch
    # bei chunked Transfer ohne Content-Length).
    stuecke, gesamt = [], 0
    async for stueck in request.stream():
        gesamt += len(stueck)
        if gesamt > EINSTELLUNGEN.max_upload:
            return Response(status_code=413)
        stuecke.append(stueck)
    daten = b"".join(stuecke)
    knoten = await speicher.datei_hochladen(benutzer["id"], parent, name, daten)
    await suche.indexieren(benutzer["id"], knoten["id"], name, daten)
    return Response(status_code=204 if existierte else 201)


async def _delete(request, benutzer, pfad) -> Response:
    speicher = request.app.state.speicher
    knoten = await speicher.knoten_per_pfad(benutzer["id"], pfad)
    if not knoten or knoten["geloescht"]:
        return Response(status_code=404)
    await speicher.loeschen(benutzer["id"], knoten["id"])
    return Response(status_code=204)


async def _mkcol(request, benutzer, pfad) -> Response:
    speicher = request.app.state.speicher
    eltern, name = _eltern_und_name(pfad)
    if not name:
        return Response(status_code=400)
    parent = None
    if eltern:
        elt = await speicher.knoten_per_pfad(benutzer["id"], eltern)
        if not elt or elt["typ"] != "ordner":
            return Response(status_code=409)
        parent = elt["id"]
    try:
        await speicher.ordner_anlegen(benutzer["id"], parent, name)
    except UniqueViolation:
        return Response(status_code=405)
    return Response(status_code=201)


async def _move(request, benutzer, pfad) -> Response:
    speicher = request.app.state.speicher
    ziel_pfad = _ziel_pfad(request.headers.get("destination", ""))
    if ziel_pfad is None or not ziel_pfad.strip("/"):
        return Response(status_code=400)
    knoten = await speicher.knoten_per_pfad(benutzer["id"], pfad)
    if not knoten or knoten["geloescht"]:
        return Response(status_code=404)
    ziel_eltern, ziel_name = _eltern_und_name(ziel_pfad)
    neuer_parent = None
    if ziel_eltern:
        elt = await speicher.knoten_per_pfad(benutzer["id"], ziel_eltern)
        if not elt or elt["typ"] != "ordner":
            return Response(status_code=409)
        neuer_parent = elt["id"]
    try:
        ergebnis = await speicher.umziehen(benutzer["id"], knoten["id"], neuer_parent, ziel_name)
    except (ValueError, UniqueViolation):
        return Response(status_code=409)
    if not ergebnis:
        return Response(status_code=404)
    return Response(status_code=201)


async def webdav_endpoint(request: Request) -> Response:
    if request.method == "OPTIONS":
        return _options()
    benutzer = await _auth(request)
    if not benutzer:
        return _401()
    pfad = unquote(request.path_params.get("pfad", ""))
    m = request.method
    if m == "PROPFIND":
        return await _propfind(request, benutzer, pfad)
    if m == "GET":
        return await _get(request, benutzer, pfad, True)
    if m == "HEAD":
        return await _get(request, benutzer, pfad, False)
    if m == "PUT":
        return await _put(request, benutzer, pfad)
    if m == "DELETE":
        return await _delete(request, benutzer, pfad)
    if m == "MKCOL":
        return await _mkcol(request, benutzer, pfad)
    if m == "MOVE":
        return await _move(request, benutzer, pfad)
    return Response(status_code=405)

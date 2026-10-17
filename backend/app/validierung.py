"""Lesbare deutsche Meldungen für ungültige Eingaben (422), eine Stelle für alle Router.

FastAPI liefert sonst eine Liste englischer Prüffehler; die Oberfläche zeigte daraus "[object Object]". Hier wird
jeder Fehler zu "Feld: Grund", die eigenen Prüfungen der Modelle (ValueError mit deutschem Text) bleiben wörtlich.
"""

from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

_FELDER = {
    "name": "Name", "parent_id": "Zielordner", "q": "Suchbegriff", "datei": "Datei", "pfad": "Pfad",
    "kennung": "Anmeldename", "passwort": "Passwort", "ids": "Auswahl", "rechte": "Rechte",
    "ziel_benutzer_id": "Konto", "unterpfad": "Unterpfad", "kante": "Größe", "stufe": "Größe",
}


def _grund(fehler: dict[str, Any]) -> str:
    art, ctx = fehler.get("type", ""), fehler.get("ctx") or {}
    if art == "value_error":
        return str(ctx.get("error") or fehler.get("msg", "")).removeprefix("Value error, ")
    if art == "missing":
        return "fehlt"
    if art == "string_too_short":
        return "darf nicht leer sein" if ctx.get("min_length") == 1 else f"mindestens {ctx.get('min_length')} Zeichen"
    if art == "string_too_long":
        return f"höchstens {ctx.get('max_length')} Zeichen"
    if art in ("too_short", "too_long"):
        return "zu wenige Einträge" if art == "too_short" else "zu viele Einträge"
    if art.startswith("uuid"):
        return "keine gültige Kennung"
    if art.startswith("int") or art.startswith("float"):
        return "keine Zahl"
    if art in ("greater_than_equal", "greater_than"):
        return f"mindestens {ctx.get('ge', ctx.get('gt'))}"
    if art in ("less_than_equal", "less_than"):
        return f"höchstens {ctx.get('le', ctx.get('lt'))}"
    if art in ("literal_error", "enum"):
        return f"erlaubt: {ctx.get('expected', '')}".strip()
    if art.startswith("bool"):
        return "nur ja oder nein"
    if art in ("json_invalid", "model_attributes_type", "dict_type"):
        return "Anfrage nicht lesbar"
    return "ungültig"


def _feld(ort: tuple) -> str:
    teile = [str(t) for t in ort if t not in ("body", "query", "path", "header", "form")]
    if not teile:
        return ""
    return _FELDER.get(teile[-1], teile[-1])


def fehlertext(fehler: list[dict[str, Any]]) -> str:
    texte = []
    for f in fehler:
        feld = _feld(tuple(f.get("loc", ())))
        texte.append(f"{feld}: {_grund(f)}" if feld else _grund(f))
    return "; ".join(dict.fromkeys(texte)) or "Eingabe ungültig"


async def validierung_behandeln(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": fehlertext(list(exc.errors()))})

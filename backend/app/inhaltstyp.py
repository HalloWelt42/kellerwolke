"""Inhaltstyp (MIME) einer Datei: vom Schreiber angegeben oder aus dem Namen; eine Stelle für alle Auslieferungen."""

from __future__ import annotations

import mimetypes

# Endungen, die mimetypes nicht oder nicht überall kennt
_EIGENE_TYPEN = {
    ".md": "text/markdown", ".vtt": "text/vtt", ".srt": "application/x-subrip", ".json": "application/json",
    ".wav": "audio/wav", ".opus": "audio/ogg", ".flac": "audio/flac", ".m4a": "audio/mp4", ".webm": "video/webm",
}


def inhaltstyp_aus_name(name: str) -> str:
    endung = ("." + name.rsplit(".", 1)[-1].lower()) if "." in name else ""
    return _EIGENE_TYPEN.get(endung) or mimetypes.guess_type(name)[0] or "application/octet-stream"


def inhaltstyp_aus_kopf(kopf: str | None, name: str) -> str:
    """Angegebener Typ des Schreibers, sonst aus dem Namen; der allgemeine Binärtyp zählt nicht als Angabe."""
    typ = (kopf or "").split(";")[0].strip().lower()
    if typ and typ != "application/octet-stream" and "/" in typ and len(typ) <= 120:
        return typ
    return inhaltstyp_aus_name(name)

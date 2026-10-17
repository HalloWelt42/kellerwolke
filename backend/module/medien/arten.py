"""Medienarten nach Dateiendung: eine Stelle für Erkennung, Auslieferung und die Kennzeichnung in Listen."""

from __future__ import annotations

from typing import Literal

Medienart = Literal["bild", "audio", "video"]

_ARTEN: dict[str, Medienart] = {
    **{e: "bild" for e in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".heic", ".heif", ".svg")},
    **{e: "audio" for e in (".mp3", ".wav", ".ogg", ".oga", ".opus", ".m4a", ".aac", ".flac")},
    **{e: "video" for e in (".mp4", ".m4v", ".mov", ".webm", ".mkv", ".ogv")},
}

# Bilder, die der Browser nicht selbst zeigt: die Vollansicht wandelt sie einmal in JPEG.
UMWANDELN = frozenset({".heic", ".heif"})
# Vektorbilder werden nicht gerastert, sondern abgeschottet ausgeliefert.
VEKTOR = frozenset({".svg"})


def endung(name: str) -> str:
    p = name.rfind(".")
    return name[p:].lower() if p > 0 else ""


def medienart(name: str) -> Medienart | None:
    return _ARTEN.get(endung(name))


def such_muster() -> list[str]:
    """LIKE-Muster aller Medienendungen, für die baumweite Medienliste."""
    return [f"%{e}" for e in sorted(_ARTEN)]

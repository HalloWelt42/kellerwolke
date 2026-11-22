"""Eigene Meldungen der Kellerwolke (Logger "kellerwolke" und darunter) auf die Standardfehlerausgabe, im Betrieb also
ins Dienstprotokoll. Der Server richtet nur seine eigenen Logger ein; ohne diese Stelle gingen Meldungen unter
WARNING verloren. Die Stufe kommt aus KELLERWOLKE_PROTOKOLL."""

import logging
import sys

from .config import EINSTELLUNGEN

NAME = "kellerwolke"


def _stufe(text: str) -> int:
    stufe = logging.getLevelName(text.strip().upper())
    return stufe if isinstance(stufe, int) else logging.INFO


def einrichten() -> None:
    """Setzt die Stufe und hängt genau eine Ausgabe an (auch wenn die App mehrfach gebaut wird, etwa in Tests)."""
    log = logging.getLogger(NAME)
    log.setLevel(_stufe(EINSTELLUNGEN.protokoll_stufe))
    if not any(getattr(h, "kellerwolke", False) for h in log.handlers):
        ausgabe = logging.StreamHandler(sys.stderr)
        ausgabe.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
        ausgabe.kellerwolke = True
        log.addHandler(ausgabe)

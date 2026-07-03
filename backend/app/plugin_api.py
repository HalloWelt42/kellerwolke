"""Plugin-SDK: die EINZIGE Schnittstelle, aus der Plugins importieren.

Ein Plugin liefert eine Funktion `register(kontext) -> PluginBeschreibung`, die
seinen APIRouter baut (mit den Depends-Funktionen aus dem Kontext) und optionale
Start/Stop-Hooks zurueckgibt. Plugins importieren NIE direkt aus app.* - so
bleibt der Kern frei aenderbar, ohne Plugins zu brechen.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from fastapi import APIRouter
from pydantic import BaseModel

if TYPE_CHECKING:  # nur fuer Typpruefung, kein Laufzeit-Import (kein Zyklus)
    from psycopg_pool import AsyncConnectionPool

    from module.auth.dienst import AuthDienst
    from module.speicher.dienst import SpeicherDienst

# Erlaubte Plugin-id: ASCII, wird zu Ordnername, Schema-Suffix (plugin_<id>),
# API-Pfadsegment und Frontend-Ordner. Die strenge Form verhindert Pfad-
# Traversal und SQL-Injection beim DROP SCHEMA.
ID_MUSTER = re.compile(r"^[a-z][a-z0-9_]{1,30}$")


class Manifest(BaseModel):
    id: str
    name: str
    version: str
    kategorie: str = "ansicht-app"  # "ansicht-app" (App-Leiste) | "dienst" (nur Server)
    icon: str = "fa-solid fa-puzzle-piece"
    backend_entry: str = "api:register"  # "<modul>:<funktion>"; leer = reines Frontend-Plugin
    frontend_entry: str = "plugin.ts"
    kern_min: str = "0.0.0"
    daten_loeschen_bei_deinstall: str = "fragen"  # fragen | loeschen | behalten
    behandelt: list[str] = []  # Medientypen, die das Plugin behandelt (z.B. ["bild","audio"]) - fuer Konflikterkennung

    def id_gueltig(self) -> bool:
        return bool(ID_MUSTER.match(self.id))


@dataclass
class PluginKontext:
    """Was ein Plugin vom Kern bekommt. Bewusst KEIN BlobStore - Plugins gehen
    ueber den SpeicherDienst, damit ETag/Journal-Konsistenz erhalten bleibt
    (gleiche Begruendung wie beim WebDAV-Adapter)."""

    manifest: Manifest
    plugin_pfad: Path
    speicher: SpeicherDienst
    auth: AuthDienst
    pool: AsyncConnectionPool  # fuer EIGENE Tabellen im Schema plugin_<id>
    aktueller_benutzer: Callable[..., Any]  # FastAPI-Dependency aus app.abhaengig
    aktueller_admin: Callable[..., Any]

    @property
    def schema(self) -> str:
        return f"plugin_{self.manifest.id}"


@dataclass
class PluginBeschreibung:
    router: APIRouter | None = None
    beim_start: Callable[[], Awaitable[None]] | None = None
    beim_stop: Callable[[], Awaitable[None]] | None = None

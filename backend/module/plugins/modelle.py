"""Pydantic-Modelle der Plugin-Verwaltung."""

from pydantic import BaseModel


class AppAus(BaseModel):
    # Schlanker Eintrag fuer die App-Leiste (nur aktive Ansichts-Apps).
    id: str
    name: str
    icon: str
    kategorie: str


class PluginAus(BaseModel):
    # Vollbild fuer das Admin-Panel.
    id: str
    name: str
    version: str
    kategorie: str
    icon: str = ""
    aktiv: bool
    defekt: str | None = None
    quelle: str


class PluginUpdate(BaseModel):
    aktiv: bool

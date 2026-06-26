"""Pydantic-Modelle der Datei-API."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


def _sauberer_name(wert: str) -> str:
    wert = wert.strip()
    if not wert:
        raise ValueError("Name darf nicht leer sein")
    if len(wert) > 255:
        raise ValueError("Name ist zu lang")
    if any(c in wert for c in "/\\\x00") or any(ord(c) < 32 for c in wert):
        raise ValueError("Name enthaelt ungueltige Zeichen")
    return wert


class KnotenAus(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: UUID
    besitzer_id: UUID
    parent_id: UUID | None = None
    name: str
    typ: str
    etag: str | None = None
    geloescht: bool
    erstellt_am: datetime
    geaendert_am: datetime
    # Groesse der aktuellen Version (Dateien); bei Ordnern/Externen None.
    groesse: int | None = None


class VersionAus(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: UUID
    groesse: int
    inhalt_hash: str
    erstellt_am: datetime


class ExternEintragAus(BaseModel):
    name: str
    ist_ordner: bool
    groesse: int


class OrdnerEingabe(BaseModel):
    name: str
    parent_id: UUID | None = None

    @field_validator("name")
    @classmethod
    def _name(cls, wert: str) -> str:
        return _sauberer_name(wert)


class UmbenennenEingabe(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def _name(cls, wert: str) -> str:
        return _sauberer_name(wert)


class VerschiebenEingabe(BaseModel):
    parent_id: UUID | None = None

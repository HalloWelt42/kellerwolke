"""Pydantic-Modelle der Datei-API."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


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


class VersionAus(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: UUID
    groesse: int
    inhalt_hash: str
    erstellt_am: datetime


class OrdnerEingabe(BaseModel):
    name: str
    parent_id: UUID | None = None


class UmbenennenEingabe(BaseModel):
    name: str


class VerschiebenEingabe(BaseModel):
    parent_id: UUID | None = None

"""Pydantic-Modelle der Admin-API (Konten-/Quota-Verwaltung, externe Quellen)."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

Rolle = Literal["admin", "mitglied"]


class ExternQuelleEingabe(BaseModel):
    besitzer_id: UUID
    name: str = Field(min_length=1, max_length=255)
    pfad: str = Field(min_length=1)
    parent_id: UUID | None = None


class BenutzerAnlegen(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    passwort: str = Field(min_length=1, max_length=1024)
    kuerzel: str | None = Field(default=None, max_length=64)
    rolle: Rolle = "mitglied"


class BenutzerUpdate(BaseModel):
    aktiv: bool | None = None
    quota_bytes: int | None = Field(default=None, ge=0)
    rolle: Rolle | None = None


class SpeicherortAus(BaseModel):
    pfad: str


class VerschiebenEingabe(BaseModel):
    ziel: str = Field(min_length=1)


class VerschiebungAus(BaseModel):
    status: str
    kopiert: int = 0
    gesamt: int = 0
    ziel: str | None = None
    fehler: str | None = None

"""Pydantic-Modelle der Admin-API (Konten-/Quota-Verwaltung)."""

from typing import Literal

from pydantic import BaseModel, Field

Rolle = Literal["admin", "mitglied"]


class BenutzerAnlegen(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    passwort: str = Field(min_length=1, max_length=1024)
    kuerzel: str | None = Field(default=None, max_length=64)
    rolle: Rolle = "mitglied"


class BenutzerUpdate(BaseModel):
    aktiv: bool | None = None
    quota_bytes: int | None = Field(default=None, ge=0)
    rolle: Rolle | None = None

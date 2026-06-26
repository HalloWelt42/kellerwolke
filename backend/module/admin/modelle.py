"""Pydantic-Modelle der Admin-API (Konten-/Quota-Verwaltung)."""

from pydantic import BaseModel


class BenutzerAnlegen(BaseModel):
    name: str
    passwort: str
    kuerzel: str | None = None
    rolle: str = "mitglied"


class BenutzerUpdate(BaseModel):
    aktiv: bool | None = None
    quota_bytes: int | None = None
    rolle: str | None = None

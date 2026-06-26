"""Pydantic-Modelle der Auth-API (keine rohen Dicts nach aussen)."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict


class LoginEingabe(BaseModel):
    kennung: str
    passwort: str


class BenutzerAus(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: UUID
    name: str
    kuerzel: str | None = None
    rolle: str
    aktiv: bool


class LoginAntwort(BaseModel):
    token: str
    benutzer: BenutzerAus


class AuthStatus(BaseModel):
    angemeldet: bool
    benutzer: BenutzerAus | None = None

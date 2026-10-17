"""Pydantic-Modelle der Auth-API (keine rohen Dicts nach aussen)."""

from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


class LoginEingabe(BaseModel):
    kennung: str
    passwort: str
    # Anmeldung an einer eigenen App: die Sitzung gilt nur zur Erkennung und für die Dateiwahl dieser App.
    fuer_app: str | None = Field(None, min_length=1, max_length=60)


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
    app: str | None = None   # die App, für die diese Anmeldung gilt (leer: die Kellerwolke selbst)

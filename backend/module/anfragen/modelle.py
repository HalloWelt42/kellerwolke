"""Ein- und Ausgaben für Aktionen der Apps und Anfragen an sie."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

Zustand = Literal["wartet", "laeuft", "fertig", "fehler", "abgebrochen"]
Art = Literal["hintergrund", "oeffnen"]
KENNUNG = r"^[a-z][a-z_]{0,39}$"
_TYP = re.compile(r"^[a-z]+/([a-z0-9.+-]+|\*)$")


class AktionEingabe(BaseModel):
    """Was eine App mit Dateien bestimmter Inhaltstypen kann."""

    kennung: str = Field(pattern=KENNUNG)
    titel: str = Field(min_length=1, max_length=60, description="etwa Transkribieren")
    titel_erneut: str | None = Field(None, max_length=60, description="wenn der Begleiter der Rolle schon da ist")
    symbol: str = Field(pattern=r"^fa-[a-z0-9-]{1,40}$", description="Symbol aus Font Awesome")
    typen: list[str] = Field(min_length=1, max_length=20, description="Inhaltstypen, auch mit Stern: audio/*")
    art: Art = "hintergrund"
    rolle: str | None = Field(None, pattern=KENNUNG, description="Begleiter, um den es geht")

    @field_validator("typen")
    @classmethod
    def _typen(cls, typen: list[str]) -> list[str]:
        typen = [t.strip().lower() for t in typen]
        for t in typen:
            if not _TYP.match(t):
                raise ValueError(f"Inhaltstyp {t!r}: etwa audio/*, video/mp4, text/markdown")
        return typen


class AktionenMeldung(BaseModel):
    adresse: str | None = Field(None, max_length=300, pattern=r"^https?://\S+$",
                                description="Oberfläche der App; nötig für Aktionen zum Öffnen")
    aktionen: list[AktionEingabe] = Field(max_length=30)


class AktionAus(BaseModel):
    """Eine Aktion, die zu einer Datei passt."""

    zugang_id: UUID
    app: str
    kennung: str
    titel: str
    symbol: str
    art: Art
    erreichbar: bool          # die App hat sich eben gemeldet; sonst wartet eine Anfrage, bis sie wieder da ist
    knoten_id: UUID           # die Datei, für die die Anfrage gilt (bei einem Begleiter seine Hauptdatei)
    erneut: bool              # der Begleiter der Rolle ist schon da


class AnfrageEingabe(BaseModel):
    zugang_id: UUID
    aktion: str = Field(pattern=KENNUNG)
    knoten_id: UUID


class WeitergabeEingabe(BaseModel):
    """Eine App gibt eine Anfrage an eine andere App desselben Kontos weiter."""

    app: str = Field(min_length=1, max_length=60)
    aktion: str = Field(pattern=KENNUNG)
    knoten_id: UUID


class StandEingabe(BaseModel):
    zustand: Literal["laeuft", "fertig", "fehler"] | None = None
    fortschritt: float | None = Field(None, ge=0, le=1)
    meldung: str | None = Field(None, max_length=300)
    ergebnis_id: UUID | None = None


class AnfrageAus(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: UUID
    app: str
    zugang_id: UUID
    aktion: str
    titel: str
    symbol: str
    art: Art
    knoten_id: UUID
    knoten_name: str
    von: str
    zustand: Zustand
    fortschritt: float | None = None
    meldung: str | None = None
    ergebnis_id: UUID | None = None
    ergebnis_name: str | None = None
    erstellt_am: datetime
    geaendert_am: datetime
    gueltig_bis: datetime
    erreichbar: bool


class AnfrageNeuAus(BaseModel):
    anfrage: AnfrageAus
    ziel: str | None = None   # bei Aktionen zum Öffnen: Adresse in der App


class WahlEintrag(BaseModel):
    """Ein Eintrag der Dateiwahl: nur Name und Eckdaten, nie Inhalt."""

    model_config = ConfigDict(extra="ignore")
    id: UUID
    name: str
    typ: str
    groesse: int | None = None
    inhaltstyp: str | None = None
    geaendert_am: datetime
    kinder_anzahl: int | None = None
    haupt_id: UUID | None = None
    rolle: str | None = None
    begleiter_anzahl: int = 0


class WahlOrt(BaseModel):
    id: UUID | None
    name: str


class WahlSeite(BaseModel):
    kette: list[WahlOrt]          # vom Konto bis zum gezeigten Ordner
    eintraege: list[WahlEintrag]


class WahlEingabe(BaseModel):
    knoten_id: UUID
    aktion: str = Field(pattern=KENNUNG)

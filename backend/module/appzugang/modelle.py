"""Ein- und Ausgaben der App-Zugänge (Verwaltung durch das Konto)."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RechtAus(BaseModel):
    knoten_id: UUID
    pfad: str
    recht: Literal["lesen", "schreiben"]


class ZugangAus(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: UUID
    app: str
    aktiv: bool
    erstellt_am: datetime
    zuletzt_genutzt: datetime | None = None
    rechte: list[RechtAus] = Field(default_factory=list)


class ZugangNeuAus(BaseModel):
    """Antwort beim Anlegen oder Erneuern: der Schlüssel steht hier einmal im Klartext und nie wieder."""

    zugang: ZugangAus
    schluessel: str


class ZugangEingabe(BaseModel):
    app: str = Field(min_length=1, max_length=60)


class AktivEingabe(BaseModel):
    aktiv: bool


class RechtEingabe(BaseModel):
    knoten_id: UUID
    recht: Literal["lesen", "schreiben"]


class RechteEingabe(BaseModel):
    rechte: list[RechtEingabe] = Field(max_length=200)

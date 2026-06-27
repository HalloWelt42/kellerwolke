"""Pydantic-Ausgabemodelle fuer die Vorgaenge-API."""

from pydantic import BaseModel


class VorgangAus(BaseModel):
    id: str
    art: str
    titel: str
    status: str
    erledigt: int
    gesamt: int
    fehler: str | None = None

"""Pydantic-Modelle der Sync-API."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AenderungAus(BaseModel):
    model_config = ConfigDict(extra="ignore")
    seq: int
    knoten_id: UUID
    typ: str
    version_id: UUID | None = None
    zeit: datetime

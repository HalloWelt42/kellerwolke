"""Pydantic-Modelle der Datei-API."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, computed_field, field_validator

from module.medien.arten import Medienart, medienart


def sauberer_name(wert: str) -> str:
    wert = wert.strip()
    if not wert:
        raise ValueError("Name darf nicht leer sein")
    if len(wert) > 255:
        raise ValueError("Name ist zu lang")
    if any(c in wert for c in "/\\\x00") or any(ord(c) < 32 for c in wert):
        raise ValueError("Name enthält ungültige Zeichen")
    return wert


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
    # Groesse der aktuellen Version (Dateien); bei Ordnern/Externen None.
    groesse: int | None = None
    # Anzahl nicht geloeschter Kinder (fuer den Ordner-Zaehler); None ausserhalb der Liste.
    kinder_anzahl: int | None = None
    # Vom Nutzer als Favorit markiert.
    favorit: bool = False
    # Mit mindestens einer anderen Person geteilt (Kennzeichen in der Liste).
    geteilt: bool = False
    # Name des Eigentuemers (nur in der Geteilt-Liste gesetzt).
    besitzer_name: str | None = None
    # Nur in Suchergebnissen: Ordnerkette über dem Treffer und ob der Name traf (sonst der Inhalt).
    ort: list[str] | None = None
    im_namen: bool | None = None
    # Begleitdateien (Liste): ein Begleiter nennt seine Hauptdatei und Rolle, eine Hauptdatei die Zahl ihrer Begleiter.
    haupt_id: UUID | None = None
    rolle: str | None = None
    begleiter_app: str | None = None       # App, die den Begleiter angelegt hat
    begleiter_anzahl: int = 0
    haupt_name: str | None = None          # Papierkorb: Hauptdatei eines allein gelöschten Begleiters

    @computed_field
    @property
    def medienart(self) -> Medienart | None:
        """Bild, Audio oder Video - die Oberfläche kennt die Endungen nicht selbst."""
        return medienart(self.name) if self.typ == "datei" else None


class TeilenEingabe(BaseModel):
    ziel_benutzer_id: UUID
    rechte: str = "lesen"


class FreigabeAus(BaseModel):
    model_config = ConfigDict(extra="ignore")
    ziel_benutzer_id: UUID
    ziel_name: str
    rechte: str


class KontoAus(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: UUID
    name: str


class SpeicherStatusAus(BaseModel):
    benutzt: int                 # durch Kellerwolke belegt (Summe der Bloecke)
    quota: int | None = None     # konto-Kontingent, falls gesetzt
    gesamt: int | None = None    # Gesamtgroesse des Datentraegers
    frei: int | None = None      # freier Platz auf dem Datentraeger
    ort: str | None = None       # aktueller Pfad des Objekt-Pools
    verfuegbar: bool = True       # ist der Objekt-Pool gerade erreichbar?


class VersionAus(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: UUID
    groesse: int
    inhalt_hash: str
    erstellt_am: datetime


class ExternEintragAus(BaseModel):
    name: str
    ist_ordner: bool
    groesse: int
    geaendert_am: datetime | None = None


class OrdnerEingabe(BaseModel):
    name: str
    parent_id: UUID | None = None

    @field_validator("name")
    @classmethod
    def _name(cls, wert: str) -> str:
        return sauberer_name(wert)


class UmbenennenEingabe(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def _name(cls, wert: str) -> str:
        return sauberer_name(wert)


class VerschiebenEingabe(BaseModel):
    parent_id: UUID | None = None


class PfadteilAus(BaseModel):
    id: UUID
    name: str


class PfadAus(BaseModel):
    """Ein aufgelöster Pfad: die Ordnerkette darüber (ohne "Meine Dateien") und der Knoten selbst."""

    kette: list[PfadteilAus]
    id: UUID
    name: str
    typ: str


class ZipEingabe(BaseModel):
    ids: list[UUID]


class ZipPlanAus(BaseModel):
    eintraege: int

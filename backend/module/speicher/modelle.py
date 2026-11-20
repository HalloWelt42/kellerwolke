"""Pydantic-Modelle der Datei-API."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator

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
    # Verweise (KW-10): ein Verweis nennt sein Original; Größe, Prüfsumme und ETag sind die des Originals. Verwaist
    # heißt: das Original fehlt oder liegt im Papierkorb. Eine Datei zählt die lebenden Verweise darauf (im
    # Papierkorb: die mit ihr gelöschten).
    ziel_id: UUID | None = None
    ziel_name: str | None = None
    verwaist: bool = False
    verweis_anzahl: int = 0
    verweis_app: str | None = None         # App, die den Verweis angelegt hat
    sha256: str | None = None              # Prüfsumme des Inhalts der aktuellen Version (KW-11)
    ziel_etag: str | None = Field(None, exclude=True)

    @model_validator(mode="after")
    def _wie_das_original(self):
        if self.typ == "verweis":
            self.etag = self.ziel_etag
        return self

    @computed_field
    @property
    def medienart(self) -> Medienart | None:
        """Bild, Audio oder Video - die Oberfläche kennt die Endungen nicht selbst; ein Verweis zeigt die Art seines
        Originals."""
        if self.typ == "verweis":
            return medienart(self.ziel_name) if self.ziel_name else None
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

    @computed_field
    @property
    def sha256(self) -> str:
        """Prüfsumme des ganzen Inhalts dieser Version (gleich inhalt_hash, unter dem Namen, den Apps erwarten)."""
        return self.inhalt_hash


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


class FolgeAus(BaseModel):
    """Ein Eintrag, den das Löschen mitnähme: ein Begleiter oder ein Verweis von anderswo, mit Pfad seines Ordners."""

    model_config = ConfigDict(extra="ignore")
    id: UUID
    name: str
    art: str                              # begleiter | verweis
    ort: str                              # Ordnerpfad ohne "Meine Dateien" (leer: oberste Ebene)
    parent_id: UUID | None = None
    rolle: str | None = None              # Begleiter: seine Rolle
    zu_id: UUID                           # die Datei, an der er hängt
    zu_name: str


class AuswahlEingabe(BaseModel):
    ids: list[UUID] = Field(min_length=1, max_length=1000)


class LoeschfolgenAus(BaseModel):
    folgen: list[FolgeAus]


class VerweisAus(BaseModel):
    """Ein Verweis auf eine Datei, mit dem Pfad seines Ordners (Detail des Originals)."""

    model_config = ConfigDict(extra="ignore")
    id: UUID
    name: str
    parent_id: UUID | None = None
    ort: str
    app: str | None = None                # App, die ihn angelegt hat
    erstellt_am: datetime

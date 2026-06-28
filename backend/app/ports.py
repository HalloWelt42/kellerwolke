"""Ports (Schnittstellen) des Speicherkerns - hexagonal, Implementierungen austauschbar.

Bewusst klein gehalten. Die Sprachwahl des Kerns ist vertagt: heute Python,
spaeter laesst sich z.B. der BlobStore-Adapter gegen Go/Rust tauschen, ohne
die Anwendungslogik zu beruehren.
"""

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


class SpeicherNichtVerfuegbar(Exception):
    """Der Objekt-Pool ist gerade nicht erreichbar: das Laufwerk ist abgehaengt
    oder der Marker passt nicht. Bewusst KEIN Schreiben/Lesen, statt still auf
    die falsche Platte (Systemplatte) auszuweichen. Die API uebersetzt das in
    HTTP 503 - der Aufrufer soll spaeter erneut versuchen, nichts geht verloren."""


@runtime_checkable
class BlobStore(Protocol):
    """Inhaltsadressierte Ablage roher Bloecke, Pool pro Nutzer isoliert."""

    def verfuegbar(self) -> bool:
        """True nur, wenn das richtige Laufwerk gemountet ist (Marker passt).
        Wird vor jedem put/get/delete geprueft; bei False -> SpeicherNichtVerfuegbar."""
        ...

    def put(self, benutzer_id: str, daten: bytes) -> tuple[str, bool]:
        """Legt die Bytes ab und liefert (hash, neu_geschrieben). Existiert der
        Block schon, wird nichts geschrieben (Dedup) und neu_geschrieben=False.
        Bei abgehaengtem Pool -> SpeicherNichtVerfuegbar (vor jedem Schreibversuch)."""
        ...

    def get(self, benutzer_id: str, blob_hash: str) -> bytes:
        ...

    def exists(self, benutzer_id: str, blob_hash: str) -> bool:
        ...

    def delete(self, benutzer_id: str, blob_hash: str) -> None:
        ...


@dataclass(frozen=True)
class Eintrag:
    """Ein Eintrag in einer externen, read-only eingehaengten Quelle."""

    name: str
    ist_ordner: bool
    groesse: int


@runtime_checkable
class Quelle(Protocol):
    """Read-only Durchreiche auf einen bestehenden Verzeichnisbaum.

    Nichts wird kopiert oder gehasht; gelesen wird direkt von der Platte.
    Im Betrieb ein gemounteter Datentraeger, lokal ein Testordner.
    """

    def auflisten(self, relativ: str) -> list[Eintrag]:
        ...

    def lesen(self, relativ: str) -> bytes:
        ...

    def info(self, relativ: str) -> Eintrag:
        ...

"""Ports (Schnittstellen) des Speicherkerns - hexagonal, Implementierungen austauschbar.

Bewusst klein gehalten. Die Sprachwahl des Kerns ist vertagt: heute Python,
spaeter laesst sich z.B. der BlobStore-Adapter gegen Go/Rust tauschen, ohne
die Anwendungslogik zu beruehren.
"""

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@runtime_checkable
class BlobStore(Protocol):
    """Inhaltsadressierte Ablage roher Bloecke, Pool pro Nutzer isoliert."""

    def put(self, benutzer_id: str, daten: bytes) -> str:
        """Legt die Bytes ab und liefert ihren Hash. Existiert der Block schon,
        wird nichts geschrieben (Dedup)."""
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
    Auf dem Live-System z.B. /mnt/tb26, lokal ein Testordner.
    """

    def auflisten(self, relativ: str) -> list[Eintrag]:
        ...

    def lesen(self, relativ: str) -> bytes:
        ...

    def info(self, relativ: str) -> Eintrag:
        ...

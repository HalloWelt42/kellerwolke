"""Vorgaenge-Registry: verfolgt Hintergrund-Jobs (z.B. Indizierung) pro Nutzer.

Bewusst prozesslokal im Speicher gehalten - passend zum Einzelprozess-Betrieb.
Jeder Vorgang laeuft als eigene asyncio-Task und ist abbrechbar. Fertige,
fehlgeschlagene oder abgebrochene Vorgaenge bleiben sichtbar, bis sie
aufgeraeumt werden. Strikt pro Nutzer gefiltert (Isolation).
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Optional


@dataclass
class Vorgang:
    id: str
    besitzer_id: str
    art: str  # z.B. "indizierung"
    titel: str
    status: str = "laeuft"  # laeuft | fertig | fehler | abgebrochen
    erledigt: int = 0  # Fortschritt in Einheiten
    gesamt: int = 0  # 0 = unbestimmt (kein Balken)
    fehler: Optional[str] = None
    task: Optional[asyncio.Task] = field(default=None, repr=False)


# So viele abgeschlossene Vorgaenge bleiben je Nutzer hoechstens sichtbar -
# damit das Dict ohne manuelles Aufraeumen nicht unbegrenzt waechst.
_MAX_FERTIG_PRO_NUTZER = 50


class VorgangRegistry:
    def __init__(self) -> None:
        self._vorgaenge: dict[str, Vorgang] = {}

    def starte(
        self,
        besitzer_id,
        art: str,
        titel: str,
        arbeit: Callable[[Vorgang], Awaitable[None]],
    ) -> Vorgang:
        """Startet einen Hintergrund-Vorgang. 'arbeit' bekommt den Vorgang und
        darf erledigt/gesamt fuer den Fortschritt setzen."""
        v = Vorgang(id=str(uuid.uuid4()), besitzer_id=str(besitzer_id), art=art, titel=titel)
        self._vorgaenge[v.id] = v
        v.task = asyncio.create_task(self._lauf(v, arbeit))
        self._kappe(str(besitzer_id))
        return v

    def _kappe(self, besitzer_id: str) -> None:
        """Aelteste abgeschlossene Vorgaenge des Nutzers FIFO entfernen, wenn die
        Obergrenze ueberschritten ist. Laufende bleiben unangetastet."""
        fertig = [
            vid
            for vid, v in self._vorgaenge.items()
            if v.besitzer_id == besitzer_id and v.status != "laeuft"
        ]
        ueberzaehlig = len(fertig) - _MAX_FERTIG_PRO_NUTZER
        for vid in fertig[:max(0, ueberzaehlig)]:
            del self._vorgaenge[vid]

    async def _lauf(self, v: Vorgang, arbeit) -> None:
        try:
            await arbeit(v)
            if v.status == "laeuft":
                v.status = "fertig"
        except asyncio.CancelledError:
            v.status = "abgebrochen"
            raise
        except Exception as e:  # ein Jobfehler darf nichts anderes mitreissen
            v.status = "fehler"
            v.fehler = str(e)[:200]

    def liste(self, besitzer_id) -> list[Vorgang]:
        return [v for v in self._vorgaenge.values() if v.besitzer_id == str(besitzer_id)]

    def abbrechen(self, besitzer_id, vid: str) -> bool:
        v = self._vorgaenge.get(vid)
        if not v or v.besitzer_id != str(besitzer_id):
            return False
        if v.status == "laeuft" and v.task:
            v.task.cancel()
        return True

    def aufraeumen(self, besitzer_id) -> None:
        """Entfernt alle nicht mehr laufenden Vorgaenge des Nutzers."""
        weg = [
            vid
            for vid, v in self._vorgaenge.items()
            if v.besitzer_id == str(besitzer_id) and v.status != "laeuft"
        ]
        for vid in weg:
            del self._vorgaenge[vid]

    async def stoppen(self) -> None:
        """Bricht beim Herunterfahren alle noch laufenden Vorgaenge ab."""
        for v in self._vorgaenge.values():
            if v.task and not v.task.done():
                v.task.cancel()

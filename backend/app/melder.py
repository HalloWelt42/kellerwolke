"""Weckt Beobachter, sobald ein Konto neue Einträge im Änderungs-Journal hat.

Das Journal ruft beim Eintragen `pg_notify('kellerwolke_journal', <konto>)`; PostgreSQL stellt die Nachricht erst
beim Festschreiben zu. Der Melder lauscht auf einer eigenen Verbindung und weckt alle, die auf dieses Konto warten.
Fällt die Verbindung aus, versucht er es mit wachsender Pause erneut; Beobachter merken davon nur, dass sie erst
nach ihrem Takt nachsehen statt sofort.
"""

from __future__ import annotations

import asyncio
import logging

import psycopg

log = logging.getLogger("kellerwolke.melder")
KANAL = "kellerwolke_journal"


class JournalMelder:
    def __init__(self, dsn: str) -> None:
        self.dsn = dsn
        self._ereignisse: dict[str, asyncio.Event] = {}
        self._aufgabe: asyncio.Task | None = None

    def starten(self) -> None:
        self._aufgabe = asyncio.create_task(self._lauschen(), name="journal-melder")

    async def stoppen(self) -> None:
        if self._aufgabe:
            self._aufgabe.cancel()
            await asyncio.gather(self._aufgabe, return_exceptions=True)

    async def _lauschen(self) -> None:
        pause = 1.0
        while True:
            try:
                async with await psycopg.AsyncConnection.connect(self.dsn, autocommit=True) as conn:
                    await conn.execute(f"LISTEN {KANAL}")
                    pause = 1.0
                    async for nachricht in conn.notifies():
                        self.melden(nachricht.payload)
            except asyncio.CancelledError:
                raise
            except Exception as f:                          # Verbindung weg: später erneut, Beobachter fallen auf ihren Takt zurück
                log.warning("Journal-Melder getrennt (%s), neuer Versuch in %.0f s", f, pause)
                await asyncio.sleep(pause)
                pause = min(pause * 2, 30.0)

    def ereignis(self, konto) -> asyncio.Event:
        """Das Ereignis, auf das ein Beobachter warten wird. VOR dem Nachsehen holen, sonst geht eine Meldung
        zwischen Nachsehen und Warten verloren."""
        return self._ereignisse.setdefault(str(konto), asyncio.Event())

    def melden(self, konto: str) -> None:
        ereignis = self._ereignisse.pop(str(konto), None)
        if ereignis:
            ereignis.set()

    @staticmethod
    async def warten(ereignis: asyncio.Event, takt_s: float) -> bool:
        """True, wenn geweckt; False nach dem Takt (dann trotzdem nachsehen und ein Lebenszeichen senden)."""
        try:
            await asyncio.wait_for(ereignis.wait(), takt_s)
            return True
        except asyncio.TimeoutError:
            return False

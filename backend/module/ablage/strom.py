"""Der Körper einer Anfrage als Datei-Objekt für den Speicher-Pool.

Der Blob-Speicher schreibt in einem Faden des Speicher-Pools und liest dort stückweise mit read(n). Der Körper einer
Anfrage kommt aber asynchron in der Ereignisschleife an. Dieser Leser holt jedes Stück aus der Schleife, sobald der
Faden es braucht: die Datei geht so direkt vom Netz auf die Platte, ohne Zwischendatei und ohne ganz im Speicher zu
liegen.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator


class StromLeser:
    def __init__(self, strom: AsyncIterator[bytes], schleife: asyncio.AbstractEventLoop) -> None:
        self._strom = strom.__aiter__()
        self._schleife = schleife
        self._rest = b""
        self._ende = False

    async def _naechstes(self) -> bytes | None:
        try:
            return await self._strom.__anext__()
        except StopAsyncIteration:
            return None

    def read(self, n: int = -1) -> bytes:
        """Nur aus einem Faden außerhalb der Ereignisschleife aufrufen (dort läuft der Blob-Speicher)."""
        while not self._ende and (n < 0 or len(self._rest) < n):
            stueck = asyncio.run_coroutine_threadsafe(self._naechstes(), self._schleife).result()
            if stueck is None:
                self._ende = True
            else:
                self._rest += stueck
        if n < 0:
            aus, self._rest = self._rest, b""
        else:
            aus, self._rest = self._rest[:n], self._rest[n:]
        return aus

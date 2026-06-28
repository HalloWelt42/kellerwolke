"""Tests fuer den nicht-blockierenden Blob-I/O-Pool: das Zeitlimit greift und
der Event-Loop bleibt waehrend blockierender Platten-I/O frei (App friert nie
komplett ein)."""

import asyncio
import time

import pytest

from app.io_pool import im_thread
from app.ports import SpeicherNichtVerfuegbar


async def test_zeitlimit_wirft():
    def haengt():
        time.sleep(1)
        return "fertig"

    with pytest.raises(SpeicherNichtVerfuegbar):
        await im_thread(haengt, timeout=0.15)


async def test_event_loop_bleibt_frei():
    # Waehrend eine blockierende Funktion im Thread laeuft, muss eine andere
    # Coroutine ungestoert weiterlaufen - der Loop darf nicht einfrieren.
    ticks = 0

    async def ticker():
        nonlocal ticks
        for _ in range(5):
            await asyncio.sleep(0.05)
            ticks += 1

    def blockiert():
        time.sleep(0.3)
        return 42

    erg, _ = await asyncio.gather(im_thread(blockiert, timeout=5), ticker())
    assert erg == 42
    assert ticks == 5  # der Ticker lief waehrend der Block-I/O voll durch

"""Gebuendelter Thread-Pool fuer blockierende Blob-Ein-/Ausgabe.

Blob-I/O (Schreiben/Lesen/Loeschen auf dem Datentraeger) laeuft NICHT direkt im
Event-Loop, sondern hier in begrenzt vielen Threads. So friert eine haengende
Platte nie den Loop und damit die ganze App ein - andere Anfragen laufen weiter.
Ein Zeitlimit gibt eine festsitzende Anfrage spaetestens nach Ablauf als nicht
verfuegbar (HTTP 503) zurueck, statt ewig zu warten.

Der Pool ist prozessweit (genau einer), nicht pro Dienst-Instanz - sonst
entstuenden in Tests Dutzende Pools. Begrenzte Groesse deckelt zugleich, wie
viele Threads eine haengende Platte maximal binden kann.
"""

import asyncio
import concurrent.futures

from app.config import EINSTELLUNGEN
from app.ports import SpeicherNichtVerfuegbar

_POOL = concurrent.futures.ThreadPoolExecutor(
    max_workers=EINSTELLUNGEN.io_threads, thread_name_prefix="blob-io"
)


async def im_thread(fn, *args, timeout: float):
    """Fuehrt eine blockierende Funktion im Thread-Pool aus und wartet hoechstens
    timeout Sekunden. Bei Ablauf -> SpeicherNichtVerfuegbar (der Thread selbst
    laeuft im Hintergrund weiter, bis die Platte antwortet)."""
    loop = asyncio.get_running_loop()
    try:
        return await asyncio.wait_for(loop.run_in_executor(_POOL, fn, *args), timeout=timeout)
    except asyncio.TimeoutError:
        raise SpeicherNichtVerfuegbar("Speicher reagiert nicht (Zeitlimit ueberschritten)")


def herunterfahren() -> None:
    """Pool beim App-Stop schliessen, ohne auf festsitzende Threads zu warten."""
    _POOL.shutdown(wait=False, cancel_futures=True)

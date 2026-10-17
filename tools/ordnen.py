#!/usr/bin/env python3
"""Ordnen nach Plan auf dem Rechner der Kellerwolke: Begleitdateien an eine andere Hauptdatei hängen, Dateien in den
Papierkorb legen (Aufbau in backend/module/einspielen/ordnen.py). Endgültig gelöscht wird nie.

    backend/.venv/bin/python tools/ordnen.py <ordnung.json>               Vorschau, ändert nichts
    backend/.venv/bin/python tools/ordnen.py <ordnung.json> --ausfuehren  ausführen

Rückgabewert 1, wenn ein Schritt im Konflikt steht oder scheitert.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections import Counter
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL / "backend"))

from psycopg_pool import AsyncConnectionPool  # noqa: E402

from app.adapters.filesystem_blobstore import FilesystemBlobStore  # noqa: E402
from app.config import EINSTELLUNGEN  # noqa: E402
from module.einspielen.dienst import EinspielDienst  # noqa: E402
from module.einspielen.ordnen import Ordnung, OrdnenDienst, Stand  # noqa: E402
from module.speicher.dienst import SpeicherDienst  # noqa: E402
from module.suche.dienst import SuchDienst  # noqa: E402


def zeile(s: Stand) -> str:
    return f"{s.befund:11} {s.schritt}" + (f": {s.grund}" if s.grund else "")


async def laufen(datei: Path, ausfuehren: bool) -> int:
    ordnung = Ordnung.model_validate_json(datei.read_text(encoding="utf-8"))
    pool = AsyncConnectionPool(EINSTELLUNGEN.dsn, min_size=1, max_size=4, open=False)
    await pool.open()
    try:
        speicher = SpeicherDienst(pool, FilesystemBlobStore(EINSTELLUNGEN.objekt_pfad))
        await speicher.speicher_initialisieren(EINSTELLUNGEN.objekt_pfad)
        dienst = OrdnenDienst(EinspielDienst(pool, speicher, SuchDienst(pool), datei.parent))
        print(f"{ordnung.titel or datei.name}: {len(ordnung.schritte)} Schritte für {ordnung.konto}"
              f"{'' if ausfuehren else ' (Vorschau, es ändert sich nichts)'}")
        if ausfuehren:
            staende = await dienst.ausfuehren(ordnung, lambda s: print(zeile(s), flush=True))
        else:
            staende = await dienst.pruefen(ordnung)
            for s in staende:
                print(zeile(s))
    finally:
        await pool.close()
    summen = Counter(s.befund for s in staende)
    print("Summe: " + ", ".join(f"{n} {b}" for b, n in sorted(summen.items())))
    return 1 if summen.keys() & {"konflikt", "fehler"} else 0


def main() -> None:
    teiler = argparse.ArgumentParser(description="In der Kellerwolke nach Plan ordnen")
    teiler.add_argument("ordnung", type=Path)
    teiler.add_argument("--ausfuehren", action="store_true", help="wirklich ausführen (sonst nur Vorschau)")
    a = teiler.parse_args()
    sys.exit(asyncio.run(laufen(a.ordnung, a.ausfuehren)))


if __name__ == "__main__":
    main()

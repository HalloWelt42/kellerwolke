#!/usr/bin/env python3
"""Einspielen nach einem Plan, auf dem Rechner der Kellerwolke neben der laufenden App (gleiche Datenbank und Ablage,
alles durch den Speicherdienst). Plan und Dateien liegen in einem Ordner; was der Plan ist, steht in
backend/module/einspielen/plan.py.

    backend/.venv/bin/python tools/einspielen.py <ordner>/plan.json               Vorschau, ändert nichts
    backend/.venv/bin/python tools/einspielen.py <ordner>/plan.json --ausfuehren  einspielen

Verbindung und Ablage kommen aus der .env des Projekts wie bei der App. Je Eintrag eine Zeile, am Ende die Summen;
Rückgabewert 1, wenn etwas fehlt, im Konflikt steht oder scheitert.
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
from module.einspielen.plan import Ergebnis, Plan  # noqa: E402
from module.speicher.dienst import SpeicherDienst  # noqa: E402
from module.suche.dienst import SuchDienst  # noqa: E402


def zeile(e: Ergebnis) -> str:
    staende = f" ({e.staende} Stände)" if e.staende > 1 else ""
    grund = f": {e.grund}" if e.grund else ""
    return f"{e.befund:11} {e.ziel}{staende}{grund}"


async def laufen(plan_datei: Path, ausfuehren: bool) -> int:
    plan = Plan.model_validate_json(plan_datei.read_text(encoding="utf-8"))
    pool = AsyncConnectionPool(EINSTELLUNGEN.dsn, min_size=1, max_size=4, open=False)
    await pool.open()
    try:
        speicher = SpeicherDienst(pool, FilesystemBlobStore(EINSTELLUNGEN.objekt_pfad))
        await speicher.speicher_initialisieren(EINSTELLUNGEN.objekt_pfad)
        dienst = EinspielDienst(pool, speicher, SuchDienst(pool), plan_datei.parent)
        print(f"{plan.titel or plan_datei.name}: {len(plan.eintraege)} Einträge für {plan.konto}"
              f"{'' if ausfuehren else ' (Vorschau, es ändert sich nichts)'}")
        if ausfuehren:
            ergebnisse = await dienst.ausfuehren(plan, lambda e: print(zeile(e), flush=True))
        else:
            ergebnisse = await dienst.pruefen(plan)
            for e in ergebnisse:
                print(zeile(e))
    finally:
        await pool.close()
    summen = Counter(e.befund for e in ergebnisse)
    print("Summe: " + ", ".join(f"{n} {b}" for b, n in sorted(summen.items())))
    return 1 if summen.keys() & {"fehlt", "konflikt", "fehler"} else 0


def main() -> None:
    teiler = argparse.ArgumentParser(description="Dateien nach einem Plan in die Kellerwolke einspielen")
    teiler.add_argument("plan", type=Path, help="plan.json im Ordner mit den Dateien")
    teiler.add_argument("--ausfuehren", action="store_true", help="wirklich einspielen (sonst nur Vorschau)")
    argumente = teiler.parse_args()
    sys.exit(asyncio.run(laufen(argumente.plan, argumente.ausfuehren)))


if __name__ == "__main__":
    main()

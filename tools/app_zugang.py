#!/usr/bin/env python3
"""App-Zugang für ein Konto auf dem Rechner der Kellerwolke anlegen, ohne den Schlüssel anzuzeigen: er geht nur in eine
Datei mit den Rechten 600 (für die Einrichtung einer App, die neben der Kellerwolke läuft). Gibt es den Zugang schon,
bekommt er mit `--erneuern` einen neuen Schlüssel (der alte gilt sofort nicht mehr), sonst bleibt alles.

    backend/.venv/bin/python tools/app_zugang.py --konto admin --app Vertonung --datei /srv/vertonung/.kellerwolke
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL / "backend"))

from psycopg.rows import dict_row  # noqa: E402
from psycopg_pool import AsyncConnectionPool  # noqa: E402

from app.adapters.filesystem_blobstore import FilesystemBlobStore  # noqa: E402
from app.config import EINSTELLUNGEN  # noqa: E402
from module.appzugang.dienst import AppZugangDienst  # noqa: E402
from module.speicher.dienst import SpeicherDienst  # noqa: E402


async def konto_id(pool, name: str):
    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute("SELECT id FROM benutzer WHERE lower(name)=lower(%s) OR lower(kuerzel)=lower(%s)", (name, name))
            zeile = await cur.fetchone()
    if zeile is None:
        raise SystemExit(f"Konto {name} gibt es nicht")
    return zeile["id"]


async def laufen(konto: str, app: str, datei: Path, erneuern: bool) -> int:
    pool = AsyncConnectionPool(EINSTELLUNGEN.dsn, min_size=1, max_size=2, open=False)
    await pool.open()
    try:
        speicher = SpeicherDienst(pool, FilesystemBlobStore(EINSTELLUNGEN.objekt_pfad))
        dienst = AppZugangDienst(pool, speicher)
        benutzer = await konto_id(pool, konto)
        vorhanden = next((z for z in await dienst.liste(benutzer) if z["app"].lower() == app.lower()), None)
        if vorhanden is None:
            _, schluessel = await dienst.anlegen(benutzer, app)
            was = "angelegt"
        elif erneuern:
            schluessel = await dienst.erneuern(benutzer, vorhanden["id"])
            was = "erneuert"
        else:
            print(f"Zugang {app} gibt es schon für {konto}; mit --erneuern bekommt er einen neuen Schlüssel")
            return 1
    finally:
        await pool.close()
    alt = os.umask(0o077)
    try:
        datei.write_text(schluessel + "\n", encoding="utf-8")
    finally:
        os.umask(alt)
    os.chmod(datei, 0o600)
    print(f"Zugang {app} für {konto} {was}; Schlüssel in {datei} (600)")
    return 0


def main() -> None:
    teiler = argparse.ArgumentParser(description="App-Zugang anlegen, Schlüssel nur in eine Datei")
    teiler.add_argument("--konto", required=True)
    teiler.add_argument("--app", required=True)
    teiler.add_argument("--datei", required=True, type=Path)
    teiler.add_argument("--erneuern", action="store_true")
    a = teiler.parse_args()
    sys.exit(asyncio.run(laufen(a.konto, a.app, a.datei, a.erneuern)))


if __name__ == "__main__":
    main()

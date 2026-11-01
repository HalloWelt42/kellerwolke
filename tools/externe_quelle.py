#!/usr/bin/env python3
"""Externe Quelle für ein Konto auf dem Rechner der Kellerwolke einhängen, ohne Anmeldung in der Oberfläche: derselbe
Weg wie die Verwaltung (SpeicherDienst.externe_quelle_anlegen), nur lesend durchgereicht, nichts wird kopiert. Gibt es
für das Konto schon eine Quelle mit diesem Namen oder diesem Pfad, bleibt alles, wie es ist.
    backend/.venv/bin/python tools/externe_quelle.py --konto admin --name "Bücher (Nachschlag)" --pfad /mnt/data/zim
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL / "backend"))

from psycopg.rows import dict_row  # noqa: E402
from psycopg_pool import AsyncConnectionPool  # noqa: E402

from app.adapters.filesystem_blobstore import FilesystemBlobStore  # noqa: E402
from app.config import EINSTELLUNGEN  # noqa: E402
from module.speicher.dienst import SpeicherDienst  # noqa: E402


async def konto_id(pool, name: str):
    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute("SELECT id FROM benutzer WHERE lower(name)=lower(%s) OR lower(kuerzel)=lower(%s)", (name, name))
            zeile = await cur.fetchone()
    if zeile is None:
        raise SystemExit(f"Konto {name} gibt es nicht")
    return zeile["id"]


async def vorhanden(pool, besitzer, name: str, pfad: str) -> str | None:
    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute("SELECT name FROM knoten WHERE besitzer_id=%s AND typ='extern' AND NOT geloescht "
                              "AND (name=%s OR extern_pfad=%s)", (besitzer, name, pfad))
            zeile = await cur.fetchone()
    return zeile["name"] if zeile else None


async def laufen(konto: str, name: str, pfad: Path) -> int:
    if not pfad.is_dir():
        print(f"Ordner {pfad} gibt es auf diesem Rechner nicht")
        return 1
    pool = AsyncConnectionPool(EINSTELLUNGEN.dsn, min_size=1, max_size=2, open=False)
    await pool.open()
    try:
        besitzer = await konto_id(pool, konto)
        schon = await vorhanden(pool, besitzer, name, str(pfad))
        if schon:
            print(f"Externe Quelle {schon} gibt es für {konto} schon; nichts geändert")
            return 0
        speicher = SpeicherDienst(pool, FilesystemBlobStore(EINSTELLUNGEN.objekt_pfad))
        await speicher.externe_quelle_anlegen(besitzer, None, name, str(pfad))
    finally:
        await pool.close()
    print(f"Externe Quelle {name} ({pfad}) für {konto} eingehängt, nur lesend")
    return 0


def main() -> None:
    teiler = argparse.ArgumentParser(description="Externe Quelle (nur lesend) für ein Konto einhängen")
    teiler.add_argument("--konto", required=True)
    teiler.add_argument("--name", required=True)
    teiler.add_argument("--pfad", required=True, type=Path)
    a = teiler.parse_args()
    sys.exit(asyncio.run(laufen(a.konto, a.name, a.pfad)))


if __name__ == "__main__":
    main()

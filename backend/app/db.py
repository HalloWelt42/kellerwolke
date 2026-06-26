"""Datenbank-Anbindung (PostgreSQL via psycopg 3) und Schema-Anwendung.

Das Schema liegt als nummerierte .sql-Dateien unter app/schema/ und wird beim
Start idempotent angewandt (CREATE TABLE IF NOT EXISTS ...).
"""

import re
from pathlib import Path

from psycopg_pool import AsyncConnectionPool

from .config import EINSTELLUNGEN

_pool: AsyncConnectionPool | None = None
SCHEMA_DIR = Path(__file__).resolve().parent / "schema"


def pool() -> AsyncConnectionPool:
    if _pool is None:
        raise RuntimeError("DB-Pool ist nicht initialisiert")
    return _pool


async def starten() -> None:
    global _pool
    _pool = AsyncConnectionPool(EINSTELLUNGEN.dsn, min_size=1, max_size=10, open=False)
    await _pool.open()
    await _schema_anwenden()


async def stoppen() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def _anweisungen(text: str) -> list[str]:
    # Zeilenkommentare entfernen (koennen Semikolons enthalten), dann splitten.
    ohne_kommentar = re.sub(r"--[^\n]*", "", text)
    return [s.strip() for s in ohne_kommentar.split(";") if s.strip()]


async def _schema_anwenden() -> None:
    if not SCHEMA_DIR.exists():
        return
    async with pool().connection() as conn:
        for sql_datei in sorted(SCHEMA_DIR.glob("*.sql")):
            for anweisung in _anweisungen(sql_datei.read_text(encoding="utf-8")):
                await conn.execute(anweisung)

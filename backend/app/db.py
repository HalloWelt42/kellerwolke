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
    """Teilt ein SQL-Skript SQL-bewusst in Einzelanweisungen.

    Beachtet Zeilen- und Blockkommentare, einfache String-Literale (mit ''
    als Escape) sowie Dollar-Quoting ($tag$...$tag$), damit Semikolons oder
    '--' innerhalb dieser Konstrukte nicht falsch zerlegt werden.
    """
    anweisungen = []
    aktuell = []
    i, n = 0, len(text)
    while i < n:
        zwei = text[i:i + 2]
        if zwei == "--":
            j = text.find("\n", i)
            i = n if j == -1 else j
            continue
        if zwei == "/*":
            j = text.find("*/", i + 2)
            i = n if j == -1 else j + 2
            continue
        zeichen = text[i]
        if zeichen == "'":
            aktuell.append(zeichen)
            i += 1
            while i < n:
                if text[i] == "'":
                    if i + 1 < n and text[i + 1] == "'":
                        aktuell.append("''")
                        i += 2
                        continue
                    aktuell.append("'")
                    i += 1
                    break
                aktuell.append(text[i])
                i += 1
            continue
        if zeichen == "$":
            marke = re.match(r"\$[A-Za-z0-9_]*\$", text[i:])
            if marke:
                tag = marke.group(0)
                ende = text.find(tag, i + len(tag))
                if ende == -1:
                    aktuell.append(text[i:])
                    i = n
                else:
                    aktuell.append(text[i:ende + len(tag)])
                    i = ende + len(tag)
                continue
        if zeichen == ";":
            stmt = "".join(aktuell).strip()
            if stmt:
                anweisungen.append(stmt)
            aktuell = []
            i += 1
            continue
        aktuell.append(zeichen)
        i += 1
    rest = "".join(aktuell).strip()
    if rest:
        anweisungen.append(rest)
    return anweisungen


async def _schema_anwenden() -> None:
    if not SCHEMA_DIR.exists():
        return
    async with pool().connection() as conn:
        for sql_datei in sorted(SCHEMA_DIR.glob("*.sql")):
            for anweisung in _anweisungen(sql_datei.read_text(encoding="utf-8")):
                await conn.execute(anweisung)

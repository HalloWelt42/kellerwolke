"""Gemeinsame Test-Fixtures. Der pool-Fixture wendet das Schema an und leert die
Tabellen vor jedem Test (lokale Entwicklungs-Datenbank)."""

import pytest
from psycopg_pool import AsyncConnectionPool

from app import db as dbmod
from app.config import EINSTELLUNGEN

TABELLEN = "benutzer, sitzung, knoten, version, blob, chunk, aenderung, freigabe, such_index"


@pytest.fixture
async def pool():
    p = AsyncConnectionPool(EINSTELLUNGEN.dsn, min_size=1, max_size=4, open=False)
    await p.open()
    async with p.connection() as conn:
        for datei in sorted(dbmod.SCHEMA_DIR.glob("*.sql")):
            for anweisung in dbmod._anweisungen(datei.read_text(encoding="utf-8")):
                await conn.execute(anweisung)
        await conn.execute(f"TRUNCATE {TABELLEN} RESTART IDENTITY CASCADE")
    yield p
    await p.close()

"""Gemeinsame Test-Fixtures.

Tests laufen gegen eine SEPARATE Datenbank (kellerwolke_test), damit ein
Testlauf niemals die Entwicklungs-/Live-Daten beruehrt. Die Test-DB wird bei
Bedarf angelegt; vor jedem Test werden Schema angewandt und Tabellen geleert.
"""

import psycopg
import pytest
from psycopg_pool import AsyncConnectionPool

from app import db as dbmod
from app.config import EINSTELLUNGEN

TEST_DB = "kellerwolke_test"


def _dsn(dbname: str) -> str:
    e = EINSTELLUNGEN
    return (f"host={e.db_host} port={e.db_port} dbname={dbname} "
            f"user={e.db_user} password={e.db_pass}")


def _stelle_test_db_sicher() -> None:
    with psycopg.connect(_dsn(EINSTELLUNGEN.db_name), autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname=%s", (TEST_DB,))
            if not cur.fetchone():
                cur.execute(f'CREATE DATABASE "{TEST_DB}"')


@pytest.fixture
async def pool():
    _stelle_test_db_sicher()
    p = AsyncConnectionPool(_dsn(TEST_DB), min_size=1, max_size=4, open=False)
    await p.open()
    async with p.connection() as conn:
        await dbmod.schema_aus_ordner_anwenden(conn, dbmod.SCHEMA_DIR)
        # Alle Tabellen leeren - Kern (public) UND etwaige Plugin-Schemata
        # (plugin_*). Keine Pflege-Liste mehr; neue Plugins lecken nicht
        # zwischen Tests.
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT format('%I.%I', schemaname, tablename) FROM pg_tables "
                "WHERE schemaname = 'public' OR schemaname LIKE 'plugin\\_%'"
            )
            tabellen = [r[0] for r in await cur.fetchall()]
        if tabellen:
            await conn.execute(
                f"TRUNCATE {', '.join(tabellen)} RESTART IDENTITY CASCADE"
            )
    yield p
    await p.close()

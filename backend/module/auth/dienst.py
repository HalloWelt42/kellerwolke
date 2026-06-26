"""Auth-Dienst: Konten anlegen, Anmelden, Sitzungen pruefen und beenden.

Server-Sitzungen mit Token im Header (kein Cookie, kein JWT). In der Datenbank
liegt nur der SHA256-Hash des Tokens - das Klartext-Token verlaesst nie den
Client-Austausch. Anmeldung ueber Name oder Kuerzel.
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from psycopg.rows import dict_row

from module.auth import passwort

_GUELTIG_TAGE = 30


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class AuthDienst:
    def __init__(self, pool) -> None:
        self.pool = pool

    async def benutzer_anlegen(self, name, klartext_passwort=None, rolle="mitglied"):
        passwort_hash = passwort.hash_passwort(klartext_passwort) if klartext_passwort else None
        async with self.pool.connection() as conn:
            async with conn.transaction():
                async with conn.cursor(row_factory=dict_row) as cur:
                    await cur.execute(
                        "INSERT INTO benutzer (name, passwort_hash, rolle) "
                        "VALUES (%s,%s,%s) RETURNING *",
                        (name, passwort_hash, rolle),
                    )
                    return await cur.fetchone()

    async def anmelden(self, kennung, klartext) -> str | None:
        async with self.pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    "SELECT * FROM benutzer WHERE aktiv AND "
                    "(lower(name)=lower(%s) OR lower(kuerzel)=lower(%s))",
                    (kennung, kennung),
                )
                benutzer = await cur.fetchone()
            if not benutzer or not passwort.pruefe(klartext, benutzer["passwort_hash"]):
                return None
            token = secrets.token_urlsafe(32)
            ablauf = datetime.now(timezone.utc) + timedelta(days=_GUELTIG_TAGE)
            async with conn.transaction():
                await conn.execute(
                    "INSERT INTO sitzung (token_hash, benutzer_id, ablauf) VALUES (%s,%s,%s)",
                    (_token_hash(token), benutzer["id"], ablauf),
                )
            return token

    async def sitzung_pruefen(self, token) -> dict | None:
        if not token:
            return None
        async with self.pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    "SELECT b.* FROM sitzung s JOIN benutzer b ON b.id = s.benutzer_id "
                    "WHERE s.token_hash=%s AND s.ablauf > now() AND b.aktiv",
                    (_token_hash(token),),
                )
                return await cur.fetchone()

    async def abmelden(self, token) -> None:
        if not token:
            return
        async with self.pool.connection() as conn:
            async with conn.transaction():
                await conn.execute(
                    "DELETE FROM sitzung WHERE token_hash=%s", (_token_hash(token),)
                )

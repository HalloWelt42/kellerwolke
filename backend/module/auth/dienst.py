"""Auth-Dienst: Konten anlegen, Anmelden, Sitzungen pruefen und beenden.

Server-Sitzungen mit Token im Header (kein Cookie, kein JWT). In der Datenbank
liegt nur der SHA256-Hash des Tokens - das Klartext-Token verlaesst nie den
Client-Austausch. Anmeldung ueber Name oder Kuerzel.
"""

import asyncio
import hashlib
import hmac
import secrets
import time
from datetime import datetime, timedelta, timezone

from psycopg.rows import dict_row

from module.auth import passwort

_GUELTIG_TAGE = 30

# WebDAV schickt Name und Passwort mit jeder Anfrage; ein Dateimanager stellt Hunderte davon. Eine erfolgreiche Prüfung
# gilt deshalb kurz weiter (nur im Speicher dieses Prozesses, unter einem Schlüssel, den nur er bilden kann). Ein
# gesperrtes Konto fällt sofort heraus, weil bei jedem Treffer der Kontostand gelesen wird.
_BASIS_GUELTIG_S = 300
_BASIS_HOECHSTENS = 256

# Fester Dummy-Hash: wird gegen einen unbekannten Benutzer geprueft, damit der
# Anmelde-Pfad gleich lange dauert (kein Timing-Orakel zur Benutzer-Enumeration).
_DUMMY_HASH = passwort.hash_passwort("kellerwolke-dummy")


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class AuthDienst:
    def __init__(self, pool) -> None:
        self.pool = pool
        self._basis_geheim = secrets.token_bytes(32)
        self._basis: dict[str, tuple[str, float]] = {}  # Schlüssel -> (Konto, gültig bis)

    @staticmethod
    async def _passwort_pruefen(klartext: str, gespeichert: str | None) -> bool:
        """PBKDF2 kostet bewusst Rechenzeit - im Faden, damit die Ereignisschleife derweil weiter bedient."""
        return await asyncio.to_thread(passwort.pruefe, klartext, gespeichert)

    async def benutzer_anlegen(self, name, klartext_passwort=None, rolle="mitglied", kuerzel=None):
        passwort_hash = await asyncio.to_thread(passwort.hash_passwort, klartext_passwort) if klartext_passwort else None
        async with self.pool.connection() as conn:
            async with conn.transaction():
                async with conn.cursor(row_factory=dict_row) as cur:
                    await cur.execute(
                        "INSERT INTO benutzer (name, kuerzel, passwort_hash, rolle) "
                        "VALUES (%s,%s,%s,%s) RETURNING *",
                        (name, kuerzel, passwort_hash, rolle),
                    )
                    return await cur.fetchone()

    async def liste_benutzer(self):
        async with self.pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute("SELECT * FROM benutzer ORDER BY lower(name)")
                return await cur.fetchall()

    async def benutzer_aktualisieren(self, benutzer_id, aktiv=None, quota_bytes=None, rolle=None):
        async with self.pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute("SELECT * FROM benutzer WHERE id=%s", (benutzer_id,))
                ziel = await cur.fetchone()
            if not ziel:
                return
            # Den letzten aktiven Admin nicht deaktivieren oder degradieren.
            entzieht_admin = ziel["rolle"] == "admin" and (
                aktiv is False or (rolle is not None and rolle != "admin")
            )
            if entzieht_admin:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT count(*) FROM benutzer WHERE rolle='admin' AND aktiv")
                    (anzahl,) = await cur.fetchone()
                if anzahl <= 1:
                    raise ValueError("Der letzte aktive Admin kann nicht entzogen werden")

            felder, werte = [], []
            if aktiv is not None:
                felder.append("aktiv=%s")
                werte.append(aktiv)
            if quota_bytes is not None:
                felder.append("quota_bytes=%s")
                werte.append(quota_bytes)
            if rolle is not None:
                felder.append("rolle=%s")
                werte.append(rolle)
            if not felder:
                return
            werte.append(benutzer_id)
            async with conn.transaction():
                await conn.execute(f"UPDATE benutzer SET {', '.join(felder)} WHERE id=%s", werte)

    async def anmelden(self, kennung, klartext) -> str | None:
        async with self.pool.connection() as conn:
            # Abgelaufene Sitzungen beilaeufig aufraeumen.
            async with conn.transaction():
                await conn.execute("DELETE FROM sitzung WHERE ablauf <= now()")
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    "SELECT * FROM benutzer WHERE aktiv AND "
                    "(lower(name)=lower(%s) OR lower(kuerzel)=lower(%s))",
                    (kennung, kennung),
                )
                benutzer = await cur.fetchone()
            # Immer einen Hash pruefen (echt oder Dummy) - konstante Zeit.
            gespeichert = (benutzer["passwort_hash"] if benutzer else None) or _DUMMY_HASH
            passwort_ok = await self._passwort_pruefen(klartext, gespeichert)
            if not benutzer or not benutzer["passwort_hash"] or not passwort_ok:
                return None
            token = secrets.token_urlsafe(32)
            ablauf = datetime.now(timezone.utc) + timedelta(days=_GUELTIG_TAGE)
            async with conn.transaction():
                await conn.execute(
                    "INSERT INTO sitzung (token_hash, benutzer_id, ablauf) VALUES (%s,%s,%s)",
                    (_token_hash(token), benutzer["id"], ablauf),
                )
            return token

    async def pruefe_basis(self, kennung, klartext) -> dict | None:
        """Prüfung von Name/Kürzel + Passwort (WebDAV-Basic-Auth) ohne Sitzung. Eine erfolgreiche Prüfung gilt kurz
        weiter; sonst konstante Zeit wie bei anmelden."""
        schluessel = hmac.new(self._basis_geheim, f"{kennung.lower()}\x00{klartext}".encode("utf-8"),
                              hashlib.sha256).hexdigest()
        treffer = self._basis.get(schluessel)
        if treffer and treffer[1] > time.monotonic():
            benutzer = await self._aktives_konto(treffer[0])
            if benutzer:
                return benutzer
        self._basis.pop(schluessel, None)
        async with self.pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    "SELECT * FROM benutzer WHERE aktiv AND "
                    "(lower(name)=lower(%s) OR lower(kuerzel)=lower(%s))",
                    (kennung, kennung),
                )
                benutzer = await cur.fetchone()
        gespeichert = (benutzer["passwort_hash"] if benutzer else None) or _DUMMY_HASH
        ok = await self._passwort_pruefen(klartext, gespeichert)
        if not benutzer or not benutzer["passwort_hash"] or not ok:
            return None
        if len(self._basis) >= _BASIS_HOECHSTENS:
            self._basis.pop(next(iter(self._basis)))  # ältester Eintrag zuerst
        self._basis[schluessel] = (str(benutzer["id"]), time.monotonic() + _BASIS_GUELTIG_S)
        return benutzer

    async def _aktives_konto(self, benutzer_id) -> dict | None:
        async with self.pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute("SELECT * FROM benutzer WHERE id=%s AND aktiv", (benutzer_id,))
                return await cur.fetchone()

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

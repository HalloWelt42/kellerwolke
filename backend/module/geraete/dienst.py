"""Gekoppelte Geräte.

Das Konto erzeugt am Rechner einen Kopplungscode (acht Zeichen ohne verwechselbare wie 0/O und 1/I). Das Gerät löst
ihn ohne Anmeldung ein und bekommt einen eigenen Schlüssel, den es wie ein Sitzungs-Token sendet. Ein Code gilt
`CODE_MINUTEN` lang und nur einmal; ein neuer Code des Kontos ersetzt einen noch offenen. Gespeichert werden nur die
SHA-256 von Code und Schlüssel. Ein Gerät handelt mit den Rechten des Kontos, bis es getrennt oder das Konto gesperrt
wird; "zuletzt gesehen" wird höchstens einmal je `GESEHEN_ABSTAND` geschrieben.

Falsche Codes bremst `Bremse` je Absender: nach `VERSUCHE` Fehlern in `FENSTER` ist eine Weile Schluss.
"""

from __future__ import annotations

import hashlib
import re
import secrets
import time
from datetime import datetime, timedelta, timezone

from psycopg.rows import dict_row

PRAEFIX = "kw_geraet_"
ARTEN = ("webapp", "browser")
CODE_ZEICHEN = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
CODE_LAENGE = 8
CODE_MINUTEN = 10
GESEHEN_ABSTAND = timedelta(minutes=1)
_NAME = re.compile(r"^[^\x00-\x1f]{1,60}$")


class CodeUngueltig(Exception):
    """Unbekannt, abgelaufen oder schon eingelöst."""


class ZuVieleVersuche(Exception):
    def __init__(self, sekunden: int) -> None:
        super().__init__("Zu viele falsche Codes. Versuch es in ein paar Minuten noch einmal.")
        self.sekunden = sekunden


class GeraetNichtGefunden(Exception):
    """Gibt es nicht (mehr) oder gehört einem anderen Konto."""


def _hash(wert: str) -> str:
    return hashlib.sha256(wert.encode("utf-8")).hexdigest()


def code_normal(code: str) -> str:
    """Wie getippt oder angezeigt (Leerzeichen, Bindestriche, klein) zur gespeicherten Form."""
    return re.sub(r"[^0-9A-Za-z]", "", code or "").upper()


def geraetename_pruefen(name: str) -> str:
    name = (name or "").strip()
    if not _NAME.match(name):
        raise ValueError("Gerätename: 1 bis 60 Zeichen")
    return name


def ist_geraeteschluessel(token: str) -> bool:
    return bool(token) and token.startswith(PRAEFIX)


class Bremse:
    """Merkt sich Fehlversuche je Absender im Prozess; ein Neustart vergisst sie (der Code ist ohnehin kurzlebig)."""

    VERSUCHE = 5
    FENSTER = 600.0
    SPERRE = 300.0

    def __init__(self) -> None:
        self._fehler: dict[str, list[float]] = {}
        self._gesperrt: dict[str, float] = {}

    def pruefen(self, absender: str) -> None:
        bis = self._gesperrt.get(absender, 0.0)
        jetzt = time.monotonic()
        if bis > jetzt:
            raise ZuVieleVersuche(int(bis - jetzt) + 1)
        self._gesperrt.pop(absender, None)

    def fehlschlag(self, absender: str) -> None:
        jetzt = time.monotonic()
        liste = [t for t in self._fehler.get(absender, []) if t > jetzt - self.FENSTER] + [jetzt]
        if len(liste) >= self.VERSUCHE:
            self._gesperrt[absender] = jetzt + self.SPERRE
            liste = []
        self._fehler[absender] = liste

    def erfolg(self, absender: str) -> None:
        self._fehler.pop(absender, None)


class GeraeteDienst:
    def __init__(self, pool) -> None:
        self.pool = pool
        self.bremse = Bremse()

    # --- Kopplung ------------------------------------------------------------------------------------------------

    async def kopplung_starten(self, benutzer_id) -> tuple[dict, str]:
        """Neuer Code für das Konto; ein noch offener verfällt. Liefert (Kopplung, Code im Klartext)."""
        code = "".join(secrets.choice(CODE_ZEICHEN) for _ in range(CODE_LAENGE))
        ablauf = datetime.now(timezone.utc) + timedelta(minutes=CODE_MINUTEN)
        async with self.pool.connection() as conn:
            async with conn.transaction():
                await conn.execute("DELETE FROM kopplung WHERE benutzer_id=%s AND eingeloest_am IS NULL", (benutzer_id,))
                async with conn.cursor(row_factory=dict_row) as cur:
                    await cur.execute(
                        "INSERT INTO kopplung (benutzer_id, code_hash, ablauf) VALUES (%s,%s,%s) RETURNING *",
                        (benutzer_id, _hash(code), ablauf))
                    return await cur.fetchone(), code

    async def kopplung_stand(self, benutzer_id, kopplung_id) -> tuple[dict, dict | None]:
        """(Kopplung, eingekoppeltes Gerät oder None)."""
        async with self.pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute("SELECT * FROM kopplung WHERE id=%s AND benutzer_id=%s", (kopplung_id, benutzer_id))
                kopplung = await cur.fetchone()
                if not kopplung:
                    raise GeraetNichtGefunden("Kopplung nicht gefunden")
                geraet = None
                if kopplung["geraet_id"]:
                    await cur.execute("SELECT * FROM geraet WHERE id=%s", (kopplung["geraet_id"],))
                    geraet = await cur.fetchone()
        return kopplung, geraet

    async def kopplung_abbrechen(self, benutzer_id, kopplung_id) -> None:
        async with self.pool.connection() as conn:
            async with conn.transaction():
                cur = await conn.execute(
                    "DELETE FROM kopplung WHERE id=%s AND benutzer_id=%s AND eingeloest_am IS NULL",
                    (kopplung_id, benutzer_id))
                if cur.rowcount == 0:
                    raise GeraetNichtGefunden("Kopplung nicht gefunden")

    async def koppeln(self, code: str, name: str, art: str, absender: str, app: str | None = None) -> tuple[dict, str, dict]:
        """Löst einen Code ein. Liefert (Gerät, Schlüssel im Klartext, Konto). Mit app gilt der Schlüssel nur als
        Anmeldung an dieser App (siehe Schema 021)."""
        self.bremse.pruefen(absender)
        name = geraetename_pruefen(name)
        if art not in ARTEN:
            raise ValueError("Unbekannte Geräteart")
        schluessel = PRAEFIX + secrets.token_urlsafe(32)
        async with self.pool.connection() as conn:
            async with conn.transaction():
                async with conn.cursor(row_factory=dict_row) as cur:
                    await cur.execute(
                        "SELECT k.id, k.benutzer_id FROM kopplung k JOIN benutzer b ON b.id = k.benutzer_id "
                        "WHERE k.code_hash=%s AND k.ablauf > now() AND k.eingeloest_am IS NULL AND b.aktiv "
                        "FOR UPDATE OF k", (_hash(code_normal(code)),))
                    kopplung = await cur.fetchone()
                    if not kopplung:
                        self.bremse.fehlschlag(absender)
                        raise CodeUngueltig("Dieser Code gilt nicht (mehr)")
                    await cur.execute(
                        "INSERT INTO geraet (benutzer_id, name, art, schluessel_hash, zuletzt_am, zuletzt_adresse, app) "
                        "VALUES (%s,%s,%s,%s,now(),%s,%s) RETURNING *",
                        (kopplung["benutzer_id"], name, art, _hash(schluessel), absender, (app or "").strip() or None))
                    geraet = await cur.fetchone()
                    await cur.execute("UPDATE kopplung SET eingeloest_am=now(), geraet_id=%s WHERE id=%s",
                                      (geraet["id"], kopplung["id"]))
                    await cur.execute("SELECT * FROM benutzer WHERE id=%s", (kopplung["benutzer_id"],))
                    benutzer = await cur.fetchone()
        self.bremse.erfolg(absender)
        return geraet, schluessel, benutzer

    # --- Anmeldung mit dem Geräteschlüssel -----------------------------------------------------------------------

    async def pruefen(self, schluessel: str, absender: str | None) -> dict | None:
        """Das Konto zum Schlüssel (mit `geraet_id`), oder None bei unbekanntem Gerät oder gesperrtem Konto."""
        if not ist_geraeteschluessel(schluessel):
            return None
        async with self.pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    "SELECT b.*, g.id AS geraet_id, g.app AS anmeldung_app, g.zuletzt_am AS geraet_zuletzt_am, "
                    "g.zuletzt_adresse AS geraet_zuletzt_adresse "
                    "FROM geraet g JOIN benutzer b ON b.id = g.benutzer_id WHERE g.schluessel_hash=%s AND b.aktiv",
                    (_hash(schluessel),))
                benutzer = await cur.fetchone()
            if not benutzer:
                return None
            zuletzt = benutzer.pop("geraet_zuletzt_am")
            adresse = benutzer.pop("geraet_zuletzt_adresse")
            if zuletzt is None or zuletzt < datetime.now(timezone.utc) - GESEHEN_ABSTAND or (absender and absender != adresse):
                await conn.execute("UPDATE geraet SET zuletzt_am=now(), zuletzt_adresse=coalesce(%s, zuletzt_adresse) "
                                   "WHERE id=%s", (absender, benutzer["geraet_id"]))
        return benutzer

    # --- Verwaltung durch das Konto ------------------------------------------------------------------------------

    async def liste(self, benutzer_id) -> list[dict]:
        async with self.pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    "SELECT * FROM geraet WHERE benutzer_id=%s "
                    "ORDER BY zuletzt_am DESC NULLS LAST, gekoppelt_am DESC", (benutzer_id,))
                return await cur.fetchall()

    async def holen(self, benutzer_id, geraet_id) -> dict:
        async with self.pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute("SELECT * FROM geraet WHERE id=%s AND benutzer_id=%s", (geraet_id, benutzer_id))
                geraet = await cur.fetchone()
        if not geraet:
            raise GeraetNichtGefunden("Gerät nicht gefunden")
        return geraet

    async def umbenennen(self, benutzer_id, geraet_id, name: str) -> dict:
        name = geraetename_pruefen(name)
        async with self.pool.connection() as conn:
            async with conn.transaction():
                async with conn.cursor(row_factory=dict_row) as cur:
                    await cur.execute("UPDATE geraet SET name=%s WHERE id=%s AND benutzer_id=%s RETURNING *",
                                      (name, geraet_id, benutzer_id))
                    geraet = await cur.fetchone()
        if not geraet:
            raise GeraetNichtGefunden("Gerät nicht gefunden")
        return geraet

    async def trennen(self, benutzer_id, geraet_id) -> None:
        """Der Schlüssel des Geräts gilt sofort nicht mehr."""
        async with self.pool.connection() as conn:
            async with conn.transaction():
                cur = await conn.execute("DELETE FROM geraet WHERE id=%s AND benutzer_id=%s", (geraet_id, benutzer_id))
                if cur.rowcount == 0:
                    raise GeraetNichtGefunden("Gerät nicht gefunden")

    async def trennen_per_schluessel(self, schluessel: str) -> None:
        """Abmelden auf dem Gerät selbst: es trennt sich."""
        if not ist_geraeteschluessel(schluessel):
            return
        async with self.pool.connection() as conn:
            async with conn.transaction():
                await conn.execute("DELETE FROM geraet WHERE schluessel_hash=%s", (_hash(schluessel),))

    async def aufraeumen(self) -> int:
        """Abgelaufene Kopplungscodes weg (eingelöste wie offene); Geräte bleiben, bis das Konto sie trennt."""
        async with self.pool.connection() as conn:
            async with conn.transaction():
                cur = await conn.execute("DELETE FROM kopplung WHERE ablauf < now() - interval '1 hour'")
                return cur.rowcount

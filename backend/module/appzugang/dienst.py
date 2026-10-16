"""App-Zugänge: Schlüssel für eigene Apps, die ohne Browser auf die Ablage eines Kontos zugreifen.

Je App ein Schlüssel, ausgestellt vom Konto selbst. Die App handelt für dieses Konto, aber nur in den Ordnern, die
ihr Recht nennt. Beim Anlegen entstehen `Apps/<App>` (schreiben) und `Apps` (lesen) als Vorgabe; gemeinsame
Arbeitsordner gibt der Nutzer weiteren Apps zum Schreiben frei. Rechte hängen an Knoten-Kennungen und überstehen
deshalb Umbenennen und Verschieben.

Der Schlüssel verlässt den Dienst nur einmal im Klartext (beim Anlegen oder Erneuern); gespeichert wird sein SHA-256.
"""

from __future__ import annotations

import hashlib
import re
import secrets
from dataclasses import dataclass, field

from psycopg.rows import dict_row

from app.adapters.postgres_metadata import PostgresMetadataRepository

PRAEFIX = "kw_app_"
APPS_ORDNER = "Apps"
RECHTE = ("lesen", "schreiben")
_APP_NAME = re.compile(r"^[^/\\\x00-\x1f]{1,60}$")


def _hash(schluessel: str) -> str:
    return hashlib.sha256(schluessel.encode("utf-8")).hexdigest()


def _neuer_schluessel() -> str:
    return PRAEFIX + secrets.token_urlsafe(32)


def app_name_pruefen(name: str) -> str:
    name = (name or "").strip()
    if not _APP_NAME.match(name) or name.startswith(".") or name in (".", ".."):
        raise ValueError("App-Name: 1 bis 60 Zeichen, ohne / und \\, nicht mit Punkt beginnend")
    return name


@dataclass(frozen=True)
class AppAkteur:
    """Wer gerade über die Ablage-Schnittstelle zugreift: eine App für ein Konto."""

    zugang_id: str
    app: str
    benutzer: dict = field(compare=False)

    @property
    def benutzer_id(self):
        return self.benutzer["id"]


class AppZugangDienst:
    def __init__(self, pool, speicher) -> None:
        self.pool = pool
        self.speicher = speicher

    # --- Verwaltung durch das Konto ---------------------------------------------------------------------------

    async def _ordner_sicherstellen(self, besitzer_id, parent_id, name):
        async with self.pool.connection() as conn:
            vorhanden = await PostgresMetadataRepository(conn).knoten_finden(besitzer_id, parent_id, name)
        if vorhanden:
            if vorhanden["typ"] != "ordner":
                raise ValueError(f"{name} ist schon als Datei vorhanden")
            return vorhanden
        return await self.speicher.ordner_anlegen(besitzer_id, parent_id, name)

    async def anlegen(self, benutzer_id, app: str) -> tuple[dict, str]:
        """Neuer Zugang mit Vorgaberechten; liefert (Zugang, Schlüssel im Klartext)."""
        app = app_name_pruefen(app)
        apps = await self._ordner_sicherstellen(benutzer_id, None, APPS_ORDNER)
        eigen = await self._ordner_sicherstellen(benutzer_id, apps["id"], app)
        schluessel = _neuer_schluessel()
        async with self.pool.connection() as conn:
            async with conn.transaction():
                async with conn.cursor(row_factory=dict_row) as cur:
                    await cur.execute("SELECT 1 FROM app_zugang WHERE benutzer_id=%s AND lower(app)=lower(%s)",
                                      (benutzer_id, app))
                    if await cur.fetchone():
                        raise FileExistsError(f"Für {app} gibt es schon einen Zugang; erneuern statt neu anlegen")
                    await cur.execute("INSERT INTO app_zugang (benutzer_id, app, schluessel_hash) VALUES (%s,%s,%s) "
                                      "RETURNING *", (benutzer_id, app, _hash(schluessel)))
                    zugang = await cur.fetchone()
                    await cur.executemany("INSERT INTO app_recht (zugang_id, knoten_id, recht) VALUES (%s,%s,%s)",
                                          [(zugang["id"], eigen["id"], "schreiben"), (zugang["id"], apps["id"], "lesen")])
        return await self.zugang(benutzer_id, zugang["id"]), schluessel

    async def erneuern(self, benutzer_id, zugang_id) -> str:
        """Neuer Schlüssel für einen bestehenden Zugang; der alte gilt sofort nicht mehr."""
        schluessel = _neuer_schluessel()
        async with self.pool.connection() as conn:
            async with conn.transaction():
                cur = await conn.execute("UPDATE app_zugang SET schluessel_hash=%s WHERE id=%s AND benutzer_id=%s",
                                         (_hash(schluessel), zugang_id, benutzer_id))
                if cur.rowcount != 1:
                    raise FileNotFoundError("Zugang nicht gefunden")
        return schluessel

    async def zugang(self, benutzer_id, zugang_id) -> dict | None:
        for z in await self.liste(benutzer_id):
            if str(z["id"]) == str(zugang_id):
                return z
        return None

    async def liste(self, benutzer_id) -> list[dict]:
        """Alle Zugänge des Kontos mit ihren Rechten (Ordner mit Pfad)."""
        async with self.pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute("SELECT id, app, aktiv, erstellt_am, zuletzt_genutzt FROM app_zugang "
                                  "WHERE benutzer_id=%s ORDER BY lower(app)", (benutzer_id,))
                zugaenge = await cur.fetchall()
                await cur.execute("SELECT r.zugang_id, r.knoten_id, r.recht FROM app_recht r "
                                  "JOIN app_zugang z ON z.id = r.zugang_id WHERE z.benutzer_id=%s", (benutzer_id,))
                rechte = await cur.fetchall()
            repo = PostgresMetadataRepository(conn)
            for z in zugaenge:
                z["rechte"] = []
                for r in rechte:
                    if r["zugang_id"] == z["id"]:
                        z["rechte"].append({"knoten_id": r["knoten_id"], "recht": r["recht"],
                                            "pfad": "/".join(await repo.pfad_namen(r["knoten_id"]))})
                z["rechte"].sort(key=lambda r: r["pfad"].lower())
        return zugaenge

    async def rechte_setzen(self, benutzer_id, zugang_id, rechte: list[tuple]) -> dict:
        """Ersetzt alle Rechte eines Zugangs. Nur eigene, nicht gelöschte Ordner; die Wurzel nie."""
        async with self.pool.connection() as conn:
            repo = PostgresMetadataRepository(conn)
            for knoten_id, recht in rechte:
                if recht not in RECHTE:
                    raise ValueError(f"Recht {recht}: nur lesen oder schreiben")
                k = await repo.knoten_holen(knoten_id)
                if not k or k["besitzer_id"] != benutzer_id or k["geloescht"] or k["typ"] != "ordner":
                    raise ValueError("Rechte gibt es nur auf eigene Ordner")
            async with conn.transaction():
                cur = await conn.execute("SELECT 1 FROM app_zugang WHERE id=%s AND benutzer_id=%s", (zugang_id, benutzer_id))
                if not await cur.fetchone():
                    raise FileNotFoundError("Zugang nicht gefunden")
                await conn.execute("DELETE FROM app_recht WHERE zugang_id=%s", (zugang_id,))
                async with conn.cursor() as c:
                    await c.executemany("INSERT INTO app_recht (zugang_id, knoten_id, recht) VALUES (%s,%s,%s)",
                                        [(zugang_id, k, r) for k, r in rechte])
        return await self.zugang(benutzer_id, zugang_id)

    async def aktiv_setzen(self, benutzer_id, zugang_id, aktiv: bool) -> dict:
        async with self.pool.connection() as conn:
            async with conn.transaction():
                cur = await conn.execute("UPDATE app_zugang SET aktiv=%s WHERE id=%s AND benutzer_id=%s",
                                         (aktiv, zugang_id, benutzer_id))
                if cur.rowcount != 1:
                    raise FileNotFoundError("Zugang nicht gefunden")
        return await self.zugang(benutzer_id, zugang_id)

    async def loeschen(self, benutzer_id, zugang_id) -> None:
        """Entfernt den Zugang samt Rechten; die Dateien der App bleiben im Baum."""
        async with self.pool.connection() as conn:
            async with conn.transaction():
                cur = await conn.execute("DELETE FROM app_zugang WHERE id=%s AND benutzer_id=%s", (zugang_id, benutzer_id))
                if cur.rowcount != 1:
                    raise FileNotFoundError("Zugang nicht gefunden")

    # --- Prüfung bei jedem Zugriff der App --------------------------------------------------------------------

    async def pruefen(self, schluessel: str) -> AppAkteur | None:
        if not schluessel or not schluessel.startswith(PRAEFIX):
            return None
        async with self.pool.connection() as conn:
            async with conn.transaction():
                async with conn.cursor(row_factory=dict_row) as cur:
                    await cur.execute(
                        "UPDATE app_zugang z SET zuletzt_genutzt=now() FROM benutzer b "
                        "WHERE z.schluessel_hash=%s AND z.aktiv AND b.id = z.benutzer_id AND b.aktiv "
                        "RETURNING z.id AS zugang_id, z.app, z.benutzer_id", (_hash(schluessel),))
                    z = await cur.fetchone()
                    if not z:
                        return None
                    await cur.execute("SELECT * FROM benutzer WHERE id=%s", (z["benutzer_id"],))
                    benutzer = await cur.fetchone()
        return AppAkteur(zugang_id=str(z["zugang_id"]), app=z["app"], benutzer=benutzer)

    async def recht(self, akteur: AppAkteur, knoten_id) -> tuple[dict | None, str | None]:
        """(Knoten, wirksames Recht) für die App. Das Recht kommt vom Knoten selbst oder dem nächsten Ordner darüber,
        der in den Rechten steht; schreiben schließt lesen ein. Fremde, gelöschte oder unbekannte Knoten: (None, None)."""
        async with self.pool.connection() as conn:
            repo = PostgresMetadataRepository(conn)
            knoten = await repo.knoten_holen(knoten_id)
            if not knoten or knoten["besitzer_id"] != akteur.benutzer_id or knoten["geloescht"]:
                return None, None
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    "WITH RECURSIVE kette AS ("
                    "  SELECT id, parent_id, geloescht FROM knoten WHERE id=%s "
                    "  UNION ALL "
                    "  SELECT k.id, k.parent_id, k.geloescht FROM knoten k JOIN kette ON k.id = kette.parent_id"
                    ") SELECT bool_or(kette.geloescht) AS geloescht, array_agg(r.recht) FILTER (WHERE r.recht IS NOT NULL) AS rechte "
                    "FROM kette LEFT JOIN app_recht r ON r.knoten_id = kette.id AND r.zugang_id=%s",
                    (knoten_id, akteur.zugang_id))
                zeile = await cur.fetchone()
        if not zeile or zeile["geloescht"]:
            return None, None                     # liegt in einem gelöschten Ordner
        rechte = zeile["rechte"] or []
        if "schreiben" in rechte:
            return knoten, "schreiben"
        if "lesen" in rechte:
            return knoten, "lesen"
        return knoten, None

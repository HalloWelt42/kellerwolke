"""Ablage für Apps: Zugriff eigener Apps auf den Baum eines Kontos, geprüft gegen die Rechte ihres Zugangs.

Eine App sieht nur, was ihr Recht abdeckt; alles andere gibt es für sie nicht (404, auch wenn es existiert). Liegt
ein Knoten im Lesebereich, aber nicht im Schreibbereich, wird Schreiben mit 403 abgewiesen. Die eigentliche
Dateiarbeit erledigt der Speicherdienst des Kerns.
"""

from __future__ import annotations

from app.adapters.postgres_metadata import PostgresMetadataRepository
from module.appzugang.dienst import AppAkteur, AppZugangDienst
from module.speicher.dienst import Bedingung

MAX_SEITE = 500


class Unsichtbar(Exception):
    """Knoten existiert nicht oder liegt außerhalb der Rechte (404)."""


class KeinSchreibrecht(Exception):
    """Lesen ja, schreiben nein (403)."""


class VorbedingungFehlt(Exception):
    """Überschreiben ohne Angabe des gelesenen Stands (428): Apps überschreiben nur mit If-Match."""


def name_pruefen(name: str) -> str:
    """Ein Namensteil eines Pfads: nicht leer, kein Schrägstrich, keine Steuerzeichen, nicht . oder .."""
    name = (name or "").strip()
    if not name or name in (".", "..") or "/" in name or "\\" in name or len(name) > 255 \
            or any(ord(c) < 32 for c in name):
        raise ValueError(f"Ungültiger Name: {name!r}")
    return name


def pfad_teile(pfad: str) -> list[str]:
    return [name_pruefen(t) for t in (pfad or "").split("/") if t.strip()]


def _hoeher(a: str | None, b: str | None) -> str | None:
    if "schreiben" in (a, b):
        return "schreiben"
    if "lesen" in (a, b):
        return "lesen"
    return None


class AblageDienst:
    def __init__(self, pool, speicher, zugang: AppZugangDienst) -> None:
        self.pool = pool
        self.speicher = speicher
        self.zugang = zugang

    async def mit_recht(self, akteur: AppAkteur, knoten_id, noetig: str = "lesen") -> tuple[dict, str]:
        knoten, recht = await self.zugang.recht(akteur, knoten_id)
        if knoten is None or recht is None:
            raise Unsichtbar("Nicht gefunden")
        if noetig == "schreiben" and recht != "schreiben":
            raise KeinSchreibrecht("Kein Schreibrecht in diesem Ordner")
        return knoten, recht

    async def _ansicht(self, knoten: dict, recht: str) -> dict:
        async with self.pool.connection() as conn:
            repo = PostgresMetadataRepository(conn)
            pfad = "/".join(await repo.pfad_namen(knoten["id"]))
            groesse = None
            if knoten["typ"] == "datei" and knoten["aktuelle_version_id"]:
                version = await repo.version_holen(knoten["aktuelle_version_id"])
                groesse = version["groesse"] if version else None
        return {**knoten, "pfad": pfad, "recht": recht, "groesse": groesse}

    async def knoten(self, akteur: AppAkteur, knoten_id) -> dict:
        return await self._ansicht(*await self.mit_recht(akteur, knoten_id))

    async def pfad_aufloesen(self, akteur: AppAkteur, pfad: str) -> dict:
        teile = pfad_teile(pfad)
        if not teile:
            raise Unsichtbar("Die Wurzel ist für Apps nicht zugänglich")
        knoten = await self.speicher.knoten_per_pfad(akteur.benutzer_id, "/".join(teile))
        if not knoten:
            raise Unsichtbar("Nicht gefunden")
        return await self.knoten(akteur, knoten["id"])

    async def kinder(self, akteur: AppAkteur, knoten_id, ab: int = 0, anzahl: int = 200) -> list[dict]:
        ordner, recht = await self.mit_recht(akteur, knoten_id)
        if ordner["typ"] != "ordner":
            raise ValueError("Kein Ordner")
        anzahl = max(1, min(anzahl, MAX_SEITE))
        async with self.pool.connection() as conn:
            repo = PostgresMetadataRepository(conn)
            basis = "/".join(await repo.pfad_namen(ordner["id"]))
            kinder = await repo.kinder_seite(ordner["id"], max(0, ab), anzahl)
            eigene = {}
            if kinder:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT knoten_id, recht FROM app_recht WHERE zugang_id=%s AND knoten_id = ANY(%s)",
                                      (akteur.zugang_id, [k["id"] for k in kinder]))
                    eigene = {k: r for k, r in await cur.fetchall()}
        return [{**k, "pfad": f"{basis}/{k['name']}", "recht": _hoeher(recht, eigene.get(k["id"]))} for k in kinder]

    async def ordner_anlegen(self, akteur: AppAkteur, pfad: str) -> dict:
        """Legt fehlende Ordner entlang des Pfads an (wie mkdir -p). Anlegen braucht Schreibrecht im jeweiligen
        Elternordner; vorhandene Ordner auf dem Weg werden nur durchlaufen."""
        teile = pfad_teile(pfad)
        if not teile:
            raise ValueError("Pfad fehlt")
        aktuell = None
        for teil in teile:
            async with self.pool.connection() as conn:
                gefunden = await PostgresMetadataRepository(conn).knoten_finden(akteur.benutzer_id, aktuell, teil)
            if gefunden:
                if gefunden["typ"] != "ordner":
                    raise FileExistsError(f"{teil} ist eine Datei, kein Ordner")
                aktuell = gefunden["id"]
                continue
            if aktuell is None:
                raise Unsichtbar("Ordner auf oberster Ebene legt nur das Konto selbst an")
            await self.mit_recht(akteur, aktuell, "schreiben")
            aktuell = (await self.speicher.ordner_anlegen(akteur.benutzer_id, aktuell, teil))["id"]
        return await self.knoten(akteur, aktuell)

    async def datei_schreiben(self, akteur: AppAkteur, pfad: str, quelle, max_bytes: int,
                              etag: str | None = None, nur_neu: bool = False) -> tuple[dict, str, int]:
        """Legt eine Datei an oder schreibt eine neue Version. Der Elternordner muss existieren und beschreibbar sein.
        Eine vorhandene Datei überschreibt eine App nur mit dem zuletzt gelesenen Stand (etag) oder gar nicht
        (nur_neu); geprüft wird endgültig im Speicherkern unter Sperre. Liefert (Knoten, Blob-Hash, Größe)."""
        teile = pfad_teile(pfad)
        if len(teile) < 2:
            raise Unsichtbar("Dateien legen Apps nur in Ordnern an")
        eltern = await self.speicher.knoten_per_pfad(akteur.benutzer_id, "/".join(teile[:-1]))
        if not eltern:
            raise Unsichtbar("Ordner nicht gefunden")
        eltern, _ = await self.mit_recht(akteur, eltern["id"], "schreiben")
        if eltern["typ"] != "ordner":
            raise ValueError("Ziel ist kein Ordner")
        async with self.pool.connection() as conn:
            vorhanden = await PostgresMetadataRepository(conn).knoten_finden(akteur.benutzer_id, eltern["id"], teile[-1])
        if vorhanden and vorhanden["typ"] != "datei":
            raise FileExistsError(f"{teile[-1]} ist ein Ordner")
        if vorhanden and etag is None and not nur_neu:
            raise VorbedingungFehlt("Die Datei gibt es schon: überschreiben nur mit If-Match (zuletzt gelesener ETag)")
        knoten, blob_hash, groesse = await self.speicher.datei_hochladen_strom(
            akteur.benutzer_id, eltern["id"], teile[-1], quelle, max_bytes, Bedingung(etag=etag, nur_neu=nur_neu))
        return await self._ansicht(knoten, "schreiben"), blob_hash, groesse

    async def pfad_von(self, akteur: AppAkteur, knoten_id) -> str:
        """Pfad einer Datei, auf die die App schreiben darf (für Schreiben per Kennung)."""
        knoten, _ = await self.mit_recht(akteur, knoten_id, "schreiben")
        if knoten["typ"] != "datei":
            raise Unsichtbar("Keine Datei")
        async with self.pool.connection() as conn:
            return "/".join(await PostgresMetadataRepository(conn).pfad_namen(knoten_id))

    async def datei_kopf(self, akteur: AppAkteur, knoten_id) -> tuple[dict, int]:
        knoten, _ = await self.mit_recht(akteur, knoten_id)
        if knoten["typ"] != "datei":
            raise Unsichtbar("Keine Datei")
        return knoten, await self.speicher.datei_groesse(akteur.benutzer_id, knoten_id)

    def datei_stroemen(self, akteur: AppAkteur, knoten_id, start: int = 0, laenge: int = -1):
        """Nur nach datei_kopf aufrufen (dort ist das Recht geprüft)."""
        return self.speicher.datei_stroemen(akteur.benutzer_id, knoten_id, start, laenge)

    async def ich(self, akteur: AppAkteur) -> dict:
        zugang = await self.zugang.zugang(akteur.benutzer_id, akteur.zugang_id)
        return {"app": akteur.app, "konto": akteur.benutzer["name"], "rechte": zugang["rechte"] if zugang else []}

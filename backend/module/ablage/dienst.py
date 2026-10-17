"""Ablage für Apps: Zugriff eigener Apps auf den Baum eines Kontos, geprüft gegen die Rechte ihres Zugangs.

Eine App sieht nur, was ihr Recht abdeckt; alles andere gibt es für sie nicht (404, auch wenn es existiert). Liegt
ein Knoten im Lesebereich, aber nicht im Schreibbereich, wird Schreiben mit 403 abgewiesen. Die eigentliche
Dateiarbeit erledigt der Speicherdienst des Kerns.
"""

from __future__ import annotations

from app.adapters.postgres_metadata import PostgresMetadataRepository
from app.inhaltstyp import inhaltstyp_aus_kopf, inhaltstyp_aus_name
from module.ablage import metadaten
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


def _meta_felder(knoten: dict, meta: dict | None) -> dict:
    """Inhaltstyp, App und Felder für die Ansicht; ohne gespeicherten Typ aus dem Namen."""
    typ = (meta or {}).get("inhaltstyp")
    if knoten["typ"] == "datei" and not typ:
        typ = inhaltstyp_aus_name(knoten["name"])
    return {"inhaltstyp": typ if knoten["typ"] == "datei" else None, "app": (meta or {}).get("app"),
            "felder": (meta or {}).get("felder") or {}}


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
            meta = (await metadaten.meta_holen(conn, [knoten["id"]])).get(knoten["id"])
        return {**knoten, "pfad": pfad, "recht": recht, "groesse": groesse, **_meta_felder(knoten, meta)}

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
            metas = await metadaten.meta_holen(conn, [k["id"] for k in kinder])
            eigene = {}
            if kinder:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT knoten_id, recht FROM app_recht WHERE zugang_id=%s AND knoten_id = ANY(%s)",
                                      (akteur.zugang_id, [k["id"] for k in kinder]))
                    eigene = {k: r for k, r in await cur.fetchall()}
        return [{**k, "pfad": f"{basis}/{k['name']}", "recht": _hoeher(recht, eigene.get(k["id"])), **_meta_felder(k, metas.get(k["id"]))}
                for k in kinder]

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
                              etag: str | None = None, nur_neu: bool = False,
                              inhaltstyp: str | None = None) -> tuple[dict, str, int]:
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
        async with self.pool.connection() as conn:
            async with conn.transaction():
                await metadaten.meta_schreiben(conn, knoten["id"], inhaltstyp_aus_kopf(inhaltstyp, teile[-1]), akteur.app)
        return await self._ansicht(knoten, "schreiben"), blob_hash, groesse

    # --- Metadaten und Herkunft -------------------------------------------------------------------------------

    async def felder_setzen(self, akteur: AppAkteur, knoten_id, aenderung: dict) -> dict:
        knoten, recht = await self.mit_recht(akteur, knoten_id, "schreiben")
        async with self.pool.connection() as conn:
            async with conn.transaction():
                await metadaten.felder_mischen(conn, knoten_id, aenderung, akteur.app)
        return await self._ansicht(knoten, recht)

    async def herkunft_setzen(self, akteur: AppAkteur, zu_id, von_id, art: str) -> list[dict]:
        """zu entstand aus von (zum Beispiel ein Transkript aus einer Aufnahme). Schreibrecht auf zu, Leserecht auf von."""
        await self.mit_recht(akteur, zu_id, "schreiben")
        await self.mit_recht(akteur, von_id, "lesen")
        if str(zu_id) == str(von_id):
            raise ValueError("Eine Datei stammt nicht von sich selbst")
        async with self.pool.connection() as conn:
            async with conn.transaction():
                await metadaten.herkunft_setzen(conn, von_id, zu_id, art, akteur.app)
        return await self.herkunft(akteur, zu_id)

    async def herkunft_entfernen(self, akteur: AppAkteur, zu_id, von_id, art: str) -> None:
        await self.mit_recht(akteur, zu_id, "schreiben")
        async with self.pool.connection() as conn:
            async with conn.transaction():
                if not await metadaten.herkunft_entfernen(conn, von_id, zu_id, art):
                    raise Unsichtbar("Diesen Bezug gibt es nicht")

    async def herkunft(self, akteur: AppAkteur, knoten_id) -> list[dict]:
        """Bezüge in beide Richtungen; der jeweils andere Knoten nur, wenn die App ihn sehen darf."""
        await self.mit_recht(akteur, knoten_id)
        async with self.pool.connection() as conn:
            bezuege = await metadaten.herkunft_von(conn, knoten_id)
        aus = []
        for b in bezuege:
            anderer = b["zu_id"] if str(b["von_id"]) == str(knoten_id) else b["von_id"]
            _, recht = await self.zugang.recht(akteur, anderer)
            if recht:
                aus.append(b)
        return aus

    async def suchen(self, akteur: AppAkteur, bedingung: dict, anzahl: int = 100) -> list[dict]:
        """Dateien, deren Felder die Bedingung enthalten, soweit die App sie sehen darf."""
        if not bedingung:
            raise ValueError("Bedingung fehlt")
        anzahl = max(1, min(anzahl, MAX_SEITE))
        async with self.pool.connection() as conn:
            ids = await metadaten.suche_felder(conn, akteur.benutzer_id, bedingung, anzahl * 4)
        aus = []
        for i in ids:
            knoten, recht = await self.zugang.recht(akteur, i)
            if recht:
                aus.append(await self._ansicht(knoten, recht))
            if len(aus) >= anzahl:
                break
        return aus

    async def pfad_von(self, akteur: AppAkteur, knoten_id) -> str:
        """Pfad einer Datei, auf die die App schreiben darf (für Schreiben per Kennung)."""
        knoten, _ = await self.mit_recht(akteur, knoten_id, "schreiben")
        if knoten["typ"] != "datei":
            raise Unsichtbar("Keine Datei")
        async with self.pool.connection() as conn:
            return "/".join(await PostgresMetadataRepository(conn).pfad_namen(knoten_id))

    async def datei_kopf(self, akteur: AppAkteur, knoten_id) -> tuple[dict, int]:
        """Knoten (mit Inhaltstyp) und Größe einer lesbaren Datei."""
        knoten, recht = await self.mit_recht(akteur, knoten_id)
        if knoten["typ"] != "datei":
            raise Unsichtbar("Keine Datei")
        async with self.pool.connection() as conn:
            meta = (await metadaten.meta_holen(conn, [knoten_id])).get(knoten["id"])
        return {**knoten, **_meta_felder(knoten, meta)}, await self.speicher.datei_groesse(akteur.benutzer_id, knoten_id)

    def datei_stroemen(self, akteur: AppAkteur, knoten_id, start: int = 0, laenge: int = -1):
        """Nur nach datei_kopf aufrufen (dort ist das Recht geprüft)."""
        return self.speicher.datei_stroemen(akteur.benutzer_id, knoten_id, start, laenge)

    async def ich(self, akteur: AppAkteur) -> dict:
        zugang = await self.zugang.zugang(akteur.benutzer_id, akteur.zugang_id)
        return {"app": akteur.app, "konto": akteur.benutzer["name"], "rechte": zugang["rechte"] if zugang else []}

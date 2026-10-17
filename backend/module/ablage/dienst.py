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
from psycopg.rows import dict_row

from module.speicher import begleiter as begleiter_regeln
from module.speicher.dienst import Bedingung, Gesperrt

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


async def _sperre_holen(conn, knoten_id) -> dict | None:
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute("SELECT app, grund, seit, bis FROM sperre WHERE knoten_id=%s AND bis > now()", (knoten_id,))
        return await cur.fetchone()


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
            sperre = await _sperre_holen(conn, knoten["id"])
            gruppe = await repo.begleiter_eintrag(knoten["id"])
        return {**knoten, "pfad": pfad, "recht": recht, "groesse": groesse, "sperre": sperre,
                "haupt_id": gruppe["haupt_id"] if gruppe else None, "rolle": gruppe["rolle"] if gruppe else None,
                **_meta_felder(knoten, meta)}

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
        return await self._in_ordner_schreiben(akteur, eltern, teile[-1], quelle, max_bytes, etag, nur_neu, inhaltstyp)

    async def _in_ordner_schreiben(self, akteur: AppAkteur, eltern: dict, name: str, quelle, max_bytes: int,
                                   etag: str | None, nur_neu: bool, inhaltstyp: str | None) -> tuple[dict, str, int]:
        """Schreibt in einen Ordner, dessen Recht der Aufrufer geprüft hat."""
        if eltern["typ"] != "ordner":
            raise ValueError("Ziel ist kein Ordner")
        async with self.pool.connection() as conn:
            vorhanden = await PostgresMetadataRepository(conn).knoten_finden(akteur.benutzer_id, eltern["id"], name)
        if vorhanden and vorhanden["typ"] != "datei":
            raise FileExistsError(f"{name} ist ein Ordner")
        if vorhanden and etag is None and not nur_neu:
            raise VorbedingungFehlt("Die Datei gibt es schon: überschreiben nur mit If-Match (zuletzt gelesener ETag)")
        knoten, blob_hash, groesse = await self.speicher.datei_hochladen_strom(
            akteur.benutzer_id, eltern["id"], name, quelle, max_bytes,
            Bedingung(etag=etag, nur_neu=nur_neu, zugang_id=akteur.zugang_id))
        async with self.pool.connection() as conn:
            async with conn.transaction():
                await metadaten.meta_schreiben(conn, knoten["id"], inhaltstyp_aus_kopf(inhaltstyp, name), akteur.app)
        return await self._ansicht(knoten, "schreiben"), blob_hash, groesse

    # --- Begleitdateien (Regeln in module/speicher/begleiter.py) ---------------------------------------------

    async def begleiter(self, akteur: AppAkteur, haupt_id) -> list[dict]:
        """Begleiter einer lesbaren Hauptdatei, soweit die App sie sehen darf."""
        haupt, _ = await self.mit_recht(akteur, haupt_id)
        if haupt["typ"] != "datei":
            raise Unsichtbar("Keine Datei")
        async with self.pool.connection() as conn:
            liste = await PostgresMetadataRepository(conn).begleiter_der_haupt(haupt_id)
        aus = []
        for b in liste:
            knoten, recht = await self.zugang.recht(akteur, b["id"])
            if recht:
                aus.append(await self._ansicht(knoten, recht))
        return aus

    async def begleiter_schreiben(self, akteur: AppAkteur, haupt_id, rolle: str, zusatz: str, quelle, max_bytes: int,
                                  etag: str | None = None, nur_neu: bool = False,
                                  inhaltstyp: str | None = None) -> tuple[dict, str, int]:
        """Schreibt den Begleiter einer Rolle neben die Hauptdatei: eine neue Version, wenn es ihn gibt (dann mit
        If-Match wie jedes Überschreiben), sonst neu unter dem Namen, den die Kellerwolke vergibt. Braucht Leserecht
        auf die Hauptdatei und Schreibrecht in ihrem Ordner. Liefert (Knoten, Blob-Hash, Größe)."""
        rolle = begleiter_regeln.rolle_pruefen(rolle)
        zusatz = begleiter_regeln.zusatz_pruefen(zusatz)
        haupt, _ = await self.mit_recht(akteur, haupt_id)
        if haupt["typ"] != "datei":
            raise ValueError("Begleiter gibt es nur zu Dateien")
        if haupt["parent_id"] is None:
            raise Unsichtbar("Dateien legen Apps nur in Ordnern an")
        async with self.pool.connection() as conn:
            repo = PostgresMetadataRepository(conn)
            if await repo.begleiter_eintrag(haupt_id):
                raise ValueError(f"{haupt['name']} ist selbst ein Begleiter; Begleiter gehören an die Hauptdatei")
            vorhanden = await repo.begleiter_fuer_rolle(haupt_id, rolle)
            eltern = await repo.knoten_holen(haupt["parent_id"])
            frei = [n for n in begleiter_regeln.namen(haupt["name"], zusatz)
                    if not await repo.knoten_finden(akteur.benutzer_id, haupt["parent_id"], n)]
        if vorhanden and not vorhanden["geloescht"]:
            await self.mit_recht(akteur, vorhanden["id"], "schreiben")
            return await self._in_ordner_schreiben(akteur, eltern, vorhanden["name"], quelle, max_bytes, etag, nur_neu,
                                                   inhaltstyp)
        if not await self.darf_begleiter(akteur, haupt):
            raise KeinSchreibrecht("Kein Schreibrecht neben dieser Datei")
        if not frei:
            raise begleiter_regeln.GruppeKonflikt(f"Neben {haupt['name']} ist kein Name für {rolle} frei")
        knoten, blob_hash, groesse = await self._in_ordner_schreiben(akteur, eltern, frei[0], quelle, max_bytes, etag,
                                                                     nur_neu or etag is None, inhaltstyp)
        await self.speicher.begleiter_anhaengen(akteur.benutzer_id, haupt_id, knoten["id"], rolle, zusatz, akteur.app)
        async with self.pool.connection() as conn:
            async with conn.transaction():
                await metadaten.herkunft_setzen(conn, haupt_id, knoten["id"], rolle, akteur.app)
        return await self._ansicht(await self.speicher.knoten_des_nutzers(akteur.benutzer_id, knoten["id"]), "schreiben"), \
            blob_hash, groesse

    async def darf_begleiter(self, akteur: AppAkteur, haupt: dict) -> bool:
        """Darf die App neben dieser Datei einen Begleiter anlegen: Schreibrecht in ihrem Ordner oder eine offene
        Anfrage genau für diese Datei."""
        if akteur.anfrage is not None and str(akteur.anfrage["knoten_id"]) == str(haupt["id"]):
            return True
        if haupt["parent_id"] is None:
            return False
        _, recht = await self.zugang.recht(akteur, haupt["parent_id"])
        return recht == "schreiben"

    async def darf_weitergeben(self, akteur: AppAkteur, knoten_id) -> None:
        """Eine Anfrage an eine andere App weitergeben darf, wer die Datei lesen und neben ihr schreiben darf."""
        knoten, _ = await self.mit_recht(akteur, knoten_id)
        if not await self.darf_begleiter(akteur, knoten):
            raise KeinSchreibrecht("Kein Schreibrecht neben dieser Datei")

    async def begleiter_anhaengen(self, akteur: AppAkteur, haupt_id, rolle: str, knoten_id, zusatz: str) -> dict:
        """Macht eine vorhandene Datei der App zum Begleiter; sie kommt neben die Hauptdatei (etwa beim Umzug einer App
        von getrennten Ordnern auf einen Baum). Braucht Schreibrecht auf die Datei und im Ordner der Hauptdatei."""
        haupt, _ = await self.mit_recht(akteur, haupt_id)
        await self.mit_recht(akteur, knoten_id, "schreiben")
        if haupt["parent_id"] is None:
            raise Unsichtbar("Dateien legen Apps nur in Ordnern an")
        await self.mit_recht(akteur, haupt["parent_id"], "schreiben")
        async with self.pool.connection() as conn:
            fremd = await PostgresMetadataRepository(conn).fremde_sperre(knoten_id, akteur.zugang_id)
        if fremd:
            raise Gesperrt(fremd)
        knoten = await self.speicher.begleiter_anhaengen(akteur.benutzer_id, haupt_id, knoten_id, rolle, zusatz, akteur.app)
        async with self.pool.connection() as conn:
            async with conn.transaction():
                await metadaten.herkunft_setzen(conn, haupt_id, knoten_id, rolle, akteur.app)
        return await self._ansicht(knoten, "schreiben")

    # --- Metadaten und Herkunft -------------------------------------------------------------------------------

    async def felder_setzen(self, akteur: AppAkteur, knoten_id, aenderung: dict) -> dict:
        knoten, recht = await self.mit_recht(akteur, knoten_id, "schreiben")
        async with self.pool.connection() as conn:
            async with conn.transaction():
                fremd = await PostgresMetadataRepository(conn).fremde_sperre(knoten_id, akteur.zugang_id)
                if fremd:
                    raise Gesperrt(fremd)
                await metadaten.felder_mischen(conn, knoten_id, aenderung, akteur.app)
        return await self._ansicht(knoten, recht)

    async def loeschen(self, akteur: AppAkteur, knoten_id) -> None:
        """In den Papierkorb - endgültig entscheidet das Konto selbst. Ein freigegebener Ordner (Anker von App-Rechten)
        bleibt stehen; was eine andere App gerade gesperrt hat, ebenso (bei Ordnern: irgendwo darunter)."""
        await self.mit_recht(akteur, knoten_id, "schreiben")
        async with self.pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute("SELECT 1 AS anker FROM app_recht WHERE knoten_id=%s LIMIT 1", (knoten_id,))
                if await cur.fetchone():
                    raise KeinSchreibrecht("Ein freigegebener Ordner lässt sich nur am Rechner löschen")
                await cur.execute(
                    "WITH RECURSIVE baum AS ("
                    "  SELECT id FROM knoten WHERE id=%s "
                    "  UNION ALL SELECT k.id FROM knoten k JOIN baum b ON k.parent_id = b.id WHERE NOT k.geloescht"
                    ") SELECT app, grund, seit, bis FROM sperre "
                    "WHERE knoten_id IN (SELECT id FROM baum) AND bis > now() AND zugang_id <> %s LIMIT 1",
                    (knoten_id, akteur.zugang_id))
                fremd = await cur.fetchone()
        if fremd:
            raise Gesperrt(fremd)
        await self.speicher.loeschen(akteur.benutzer_id, knoten_id)

    # --- Bearbeitungssperre -----------------------------------------------------------------------------------

    async def sperren(self, akteur: AppAkteur, knoten_id, dauer_s: int, grund: str = "") -> dict:
        """Sperrt eine Datei für dauer_s Sekunden oder verlängert die eigene Sperre. Hält eine andere App eine gültige
        Sperre, wird abgewiesen; eine abgelaufene fremde Sperre wird übernommen."""
        knoten, _ = await self.mit_recht(akteur, knoten_id, "schreiben")
        if knoten["typ"] != "datei":
            raise ValueError("Gesperrt werden nur Dateien")
        async with self.pool.connection() as conn:
            async with conn.transaction():
                async with conn.cursor(row_factory=dict_row) as cur:
                    await cur.execute(
                        "INSERT INTO sperre (knoten_id, zugang_id, app, grund, bis) "
                        "VALUES (%s,%s,%s,%s, now() + make_interval(secs => %s)) "
                        "ON CONFLICT (knoten_id) DO UPDATE SET zugang_id=EXCLUDED.zugang_id, app=EXCLUDED.app, "
                        "grund=EXCLUDED.grund, bis=EXCLUDED.bis, "
                        "seit=CASE WHEN sperre.zugang_id = EXCLUDED.zugang_id AND sperre.bis > now() THEN sperre.seit ELSE now() END "
                        "WHERE sperre.zugang_id = EXCLUDED.zugang_id OR sperre.bis <= now() "
                        "RETURNING app, grund, seit, bis",
                        (knoten_id, akteur.zugang_id, akteur.app, grund, dauer_s))
                    sperre = await cur.fetchone()
                if sperre is None:
                    raise Gesperrt(await _sperre_holen(conn, knoten_id))
        return sperre

    async def entsperren(self, akteur: AppAkteur, knoten_id) -> None:
        """Gibt die eigene Sperre frei; ohne Sperre geschieht nichts, eine fremde gültige Sperre bleibt (423)."""
        await self.mit_recht(akteur, knoten_id, "schreiben")
        async with self.pool.connection() as conn:
            async with conn.transaction():
                await conn.execute("DELETE FROM sperre WHERE knoten_id=%s AND (zugang_id=%s OR bis <= now())",
                                   (knoten_id, akteur.zugang_id))
                fremd = await PostgresMetadataRepository(conn).fremde_sperre(knoten_id, akteur.zugang_id)
        if fremd:
            raise Gesperrt(fremd)

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

    async def datei_kopf(self, akteur: AppAkteur, knoten_id):
        """Knoten (mit Inhaltstyp) und festgehaltener Stand einer lesbaren Datei."""
        knoten, recht = await self.mit_recht(akteur, knoten_id)
        stand = await self.speicher.eigene_datei(akteur.benutzer_id, knoten_id) if knoten["typ"] == "datei" else None
        if stand is None:
            raise Unsichtbar("Keine Datei")
        async with self.pool.connection() as conn:
            meta = (await metadaten.meta_holen(conn, [knoten_id])).get(knoten["id"])
        return {**stand.knoten, **_meta_felder(stand.knoten, meta)}, stand

    async def versionen(self, akteur: AppAkteur, knoten_id) -> list[dict]:
        """Versionen einer lesbaren Datei, neueste zuerst; die aktuelle ist markiert."""
        knoten, _ = await self.mit_recht(akteur, knoten_id)
        if knoten["typ"] != "datei":
            raise Unsichtbar("Keine Datei")
        liste = await self.speicher.versionen(akteur.benutzer_id, knoten_id) or []
        return [{**v, "aktuell": v["id"] == knoten["aktuelle_version_id"]} for v in liste]

    async def version_kopf(self, akteur: AppAkteur, knoten_id, version_id):
        """Knoten und Stand einer bestimmten Version einer lesbaren Datei."""
        knoten, _ = await self.mit_recht(akteur, knoten_id)
        stand = await self.speicher.version_stand(akteur.benutzer_id, knoten_id, version_id) if knoten["typ"] == "datei" else None
        if stand is None:
            raise Unsichtbar("Version nicht gefunden")
        async with self.pool.connection() as conn:
            meta = (await metadaten.meta_holen(conn, [knoten_id])).get(knoten["id"])
        return {**stand.knoten, **_meta_felder(stand.knoten, meta)}, stand

    def stand_stroemen(self, stand, start: int = 0, laenge: int = -1):
        """Nur mit einem Stand aus datei_kopf (dort ist das Recht geprüft)."""
        return self.speicher.stand_stroemen(stand, start, laenge)

    # --- Änderungen beobachten --------------------------------------------------------------------------------

    async def aenderungen(self, akteur: AppAkteur, ordner_id, seit: int, anzahl: int = 500) -> dict:
        ordner, _ = await self.mit_recht(akteur, ordner_id)
        if ordner["typ"] != "ordner":
            raise ValueError("Kein Ordner")
        return await self.speicher.journal_im_ordner(akteur.benutzer_id, ordner_id, seit, max(1, min(anzahl, MAX_SEITE)))

    async def ereignisse(self, akteur: AppAkteur, ordner_id, seit: int, melder, verbunden, takt_s: float = 15.0):
        """Liefert Stände (wie aenderungen), sobald sich unter dem Ordner etwas ändert; None als Lebenszeichen nach
        jedem ruhigen Takt. Das Recht wird bei jeder Runde neu geprüft (ein entzogenes Recht beendet den Strom)."""
        while await verbunden():
            ereignis = melder.ereignis(akteur.benutzer_id)
            stand = await self.aenderungen(akteur, ordner_id, seit)
            if stand["eintraege"] or stand["luecke"]:
                seit = stand["bis"]
                yield stand
                continue
            seit = stand["bis"]
            if not await melder.warten(ereignis, takt_s):
                yield None

    async def ich(self, akteur: AppAkteur) -> dict:
        zugang = await self.zugang.zugang(akteur.benutzer_id, akteur.zugang_id)
        return {"app": akteur.app, "konto": akteur.benutzer["name"], "konto_id": akteur.benutzer_id,
                "rechte": zugang["rechte"] if zugang else []}

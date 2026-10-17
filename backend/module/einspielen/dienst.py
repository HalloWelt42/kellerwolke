"""Einspielen nach einem Plan (siehe plan.py), durch den Speicherdienst wie jedes Hochladen: Journal, Begleiter,
Suchindex. Regeln:

- Erst die Vorschau (`pruefen`): sie sagt je Eintrag neu, vorhanden, fortsetzen, Konflikt oder fehlt und ändert nichts.
- Nie überschreiben: liegt am Ziel etwas anderes (andere Prüfsumme, ein Ordner), bleibt es, und der Eintrag entfällt.
- Jeder Stand wird nur mit seiner Prüfsumme eingetragen; nach einem Abbruch setzt ein neuer Lauf beim nächsten Stand fort.
- Dateien des Plans liegen im Ordner des Plans; Wege aus ihm heraus werden abgewiesen.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable
from pathlib import Path, PurePosixPath

from psycopg.rows import dict_row

from app.adapters.postgres_metadata import PostgresMetadataRepository
from app.inhaltstyp import inhaltstyp_aus_kopf
from module.ablage import metadaten
from module.ablage.dienst import pfad_teile
from module.speicher import begleiter as begleiter_regeln
from module.speicher.dienst import SpeicherDienst
from module.suche.dienst import SuchDienst

from .plan import Eintrag, Ergebnis, Plan, Stand

log = logging.getLogger("kellerwolke.einspielen")
BLOCK = 1024 * 1024


class PlanFehler(ValueError):
    """Der Plan selbst ist unbrauchbar (Konto unbekannt, Wege aus dem Ordner heraus)."""


def _sha256(datei: Path) -> str:
    h = hashlib.sha256()
    with datei.open("rb") as f:
        while block := f.read(BLOCK):
            h.update(block)
    return h.hexdigest()


class EinspielDienst:
    def __init__(self, pool, speicher: SpeicherDienst, suche: SuchDienst, ordner: Path) -> None:
        self.pool = pool
        self.speicher = speicher
        self.suche = suche
        self.ordner = ordner.resolve()

    # --- Plan lesen -------------------------------------------------------------------------------------------

    def datei(self, stand: Stand) -> Path:
        """Die Datei eines Stands im Ordner des Plans; nie außerhalb."""
        pfad = (self.ordner / stand.datei).resolve()
        if not pfad.is_relative_to(self.ordner):
            raise PlanFehler(f"{stand.datei} liegt außerhalb des Plans")
        return pfad

    async def konto(self, name: str):
        async with self.pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute("SELECT id FROM benutzer WHERE lower(name)=lower(%s) OR lower(kuerzel)=lower(%s)",
                                  (name, name))
                zeile = await cur.fetchone()
        if zeile is None:
            raise PlanFehler(f"Konto {name} gibt es nicht")
        return zeile["id"]

    # --- Vorschau ---------------------------------------------------------------------------------------------

    async def pruefen(self, plan: Plan) -> list[Ergebnis]:
        besitzer = await self.konto(plan.konto)
        ziele = {e.ziel for e in plan.eintraege}
        return [await self._pruefen(besitzer, e, ziele) for e in self._reihenfolge(plan)]

    @staticmethod
    def _reihenfolge(plan: Plan) -> list[Eintrag]:
        """Hauptdateien vor ihren Begleitern."""
        return sorted(plan.eintraege, key=lambda e: e.begleitet is not None)

    async def _pruefen(self, besitzer, e: Eintrag, ziele: set[str]) -> Ergebnis:
        staende = len(e.fruehere) + 1
        try:
            teile = pfad_teile(e.ziel)
        except ValueError as f:
            return Ergebnis(ziel=e.ziel, befund="konflikt", grund=f"Ziel ungültig: {f}", staende=staende)
        if len(teile) < 2:
            return Ergebnis(ziel=e.ziel, befund="konflikt", grund="Dateien kommen in einen Ordner", staende=staende)
        for s in [*e.fruehere, e]:
            pfad = self.datei(s)
            if not pfad.is_file():
                return Ergebnis(ziel=e.ziel, befund="fehlt", grund=f"{s.datei} fehlt", staende=staende)
            if _sha256(pfad) != s.sha256:
                return Ergebnis(ziel=e.ziel, befund="fehlt", grund=f"{s.datei} hat eine andere Prüfsumme", staende=staende)
        if e.begleitet:
            grund = await self._begleitung_pruefen(besitzer, e, ziele)
            if grund:
                return Ergebnis(ziel=e.ziel, befund="konflikt", grund=grund, staende=staende)
        knoten = await self.speicher.knoten_per_pfad(besitzer, "/".join(teile))
        if knoten is None:
            return Ergebnis(ziel=e.ziel, befund="neu", staende=staende)
        if knoten["typ"] != "datei":
            return Ergebnis(ziel=e.ziel, befund="konflikt", grund="am Ziel liegt ein Ordner", staende=staende)
        aktuell = await self._aktueller_hash(knoten)
        if aktuell == e.sha256:
            if e.begleitet and not await self._ist_begleiter(knoten, e):
                return Ergebnis(ziel=e.ziel, befund="fortsetzen", grund="Gruppe fehlt noch", staende=staende)
            return Ergebnis(ziel=e.ziel, befund="vorhanden", staende=staende)
        if aktuell in [s.sha256 for s in e.fruehere]:
            return Ergebnis(ziel=e.ziel, befund="fortsetzen", grund="spätere Stände fehlen noch", staende=staende)
        return Ergebnis(ziel=e.ziel, befund="konflikt", grund="am Ziel liegt eine andere Datei", staende=staende)

    async def _begleitung_pruefen(self, besitzer, e: Eintrag, ziele: set[str]) -> str:
        b = e.begleitet
        ziel, haupt = PurePosixPath(e.ziel), PurePosixPath(b.haupt)
        try:
            begleiter_regeln.rolle_pruefen(b.rolle)
            begleiter_regeln.zusatz_pruefen(b.zusatz)
        except ValueError as f:
            return str(f)
        if ziel.parent != haupt.parent or ziel.name not in begleiter_regeln.namen(haupt.name, b.zusatz):
            return f"als Begleiter heißt die Datei {begleiter_regeln.namen(haupt.name, b.zusatz)[0]} neben {haupt.name}"
        if b.haupt not in ziele and await self.speicher.knoten_per_pfad(besitzer, b.haupt) is None:
            return f"Hauptdatei {b.haupt} fehlt"
        return ""

    async def _aktueller_hash(self, knoten) -> str | None:
        if not knoten.get("aktuelle_version_id"):
            return None
        async with self.pool.connection() as conn:
            version = await PostgresMetadataRepository(conn).version_holen(knoten["aktuelle_version_id"])
        return version["inhalt_hash"] if version else None

    async def _ist_begleiter(self, knoten, e: Eintrag) -> bool:
        async with self.pool.connection() as conn:
            eintrag = await PostgresMetadataRepository(conn).begleiter_eintrag(knoten["id"])
        return bool(eintrag) and eintrag["rolle"] == e.begleitet.rolle

    # --- Ausführen --------------------------------------------------------------------------------------------

    async def ausfuehren(self, plan: Plan, melden: Callable[[Ergebnis], None] = lambda _e: None) -> list[Ergebnis]:
        """Spielt ein, was die Vorschau als neu oder fortsetzen sieht; alles andere bleibt, wie es ist."""
        besitzer = await self.konto(plan.konto)
        ziele = {e.ziel for e in plan.eintraege}
        aus: list[Ergebnis] = []
        for e in self._reihenfolge(plan):
            befund = await self._pruefen(besitzer, e, ziele)
            if befund.befund in ("neu", "fortsetzen"):
                try:
                    await self._einspielen(besitzer, e)
                    befund = Ergebnis(ziel=e.ziel, befund="eingespielt", staende=befund.staende)
                except Exception as f:  # noqa: BLE001 - ein Eintrag hält die übrigen nicht auf
                    log.exception("Einspielen von %s", e.ziel)
                    befund = Ergebnis(ziel=e.ziel, befund="fehler", grund=f"{type(f).__name__}: {f}", staende=befund.staende)
            aus.append(befund)
            melden(befund)
        return aus

    async def _ordner(self, besitzer, teile: list[str]):
        """Die Ordnerkette unter Meine Dateien, angelegt, wo sie fehlt; liefert die Kennung des letzten."""
        eltern = None
        for teil in teile:
            async with self.pool.connection() as conn:
                knoten = await PostgresMetadataRepository(conn).knoten_finden(besitzer, eltern, teil)
            if knoten is None:
                knoten = await self.speicher.ordner_anlegen(besitzer, eltern, teil)
            elif knoten["typ"] != "ordner":
                raise FileExistsError(f"{teil} ist kein Ordner")
            eltern = knoten["id"]
        return eltern

    async def _einspielen(self, besitzer, e: Eintrag) -> None:
        teile = pfad_teile(e.ziel)
        eltern = await self._ordner(besitzer, teile[:-1])
        name = teile[-1]
        vorhanden = await self.speicher.knoten_per_pfad(besitzer, "/".join(teile))
        aktuell = await self._aktueller_hash(vorhanden) if vorhanden else None
        staende = [*e.fruehere, e]
        schon = next((i + 1 for i, s in enumerate(staende) if s.sha256 == aktuell), 0)
        knoten = vorhanden
        for s in staende[schon:]:
            with self.datei(s).open("rb") as f:
                knoten, _, _ = await self.speicher.datei_hochladen_strom(besitzer, eltern, name, f, 0, pruefsumme=s.sha256)
        async with self.pool.connection() as conn:
            async with conn.transaction():
                await metadaten.meta_schreiben(conn, knoten["id"], inhaltstyp_aus_kopf(e.inhaltstyp, name), e.app)
                if e.felder:
                    await metadaten.felder_mischen(conn, knoten["id"], e.felder, e.app)
        if e.begleitet:
            haupt = await self.speicher.knoten_per_pfad(besitzer, e.begleitet.haupt)
            await self.speicher.begleiter_anhaengen(besitzer, haupt["id"], knoten["id"], e.begleitet.rolle,
                                                    e.begleitet.zusatz, e.app)
        try:
            await self.suche.datei_indexieren(self.speicher, besitzer, knoten["id"])
        except Exception:  # noqa: BLE001 - der Index ist nachrangig, die Datei liegt
            log.exception("Index für %s", e.ziel)

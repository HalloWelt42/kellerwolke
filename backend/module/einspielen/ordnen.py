"""Ordnen nach Plan, vom Rechner der Kellerwolke aus (etwa nach einer Übernahme): eine Begleitdatei an eine andere
Hauptdatei hängen (sie zieht neben sie), eine Datei samt Begleitern in einen anderen Ordner verschieben (auf Wunsch mit
neuem Namen; die Begleiter ziehen ihren Namen nach, nichts wird kopiert) und Dateien in den Papierkorb legen. Gleiche Regeln wie beim Einspielen:
erst die Vorschau, die nichts ändert; jeder Schritt wird beim Ausführen noch einmal geprüft; endgültig gelöscht wird
nie, der Papierkorb gibt alles wieder her.

Ein Schritt "papierkorb" kann eine Prüfsumme nennen (nur genau dieser Inhalt) und legt eine Hauptdatei nur weg, wenn
ihr keine Begleiter mehr anhängen, außer solchen, die frühere Schritte desselben Plans woandershin hängen, oder wenn er
es ausdrücklich samt Begleitern verlangt (`mit_begleitern`).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import PurePosixPath
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from app.adapters.postgres_metadata import PostgresMetadataRepository
from module.speicher import begleiter as begleiter_regeln

from .dienst import EinspielDienst
from .plan import SHA256


class Umhaengen(BaseModel):
    art: Literal["begleiter"]
    datei: str = Field(min_length=1, description="Pfad der Begleitdatei jetzt")
    haupt: str = Field(min_length=1, description="Pfad der Hauptdatei, zu der sie gehört")
    rolle: str
    zusatz: str
    app: str | None = None


class Weglegen(BaseModel):
    art: Literal["papierkorb"]
    ziel: str = Field(min_length=1)
    sha256: str | None = Field(None, pattern=SHA256, description="nur wenn der Inhalt genau diese Prüfsumme hat")
    mit_begleitern: bool = Field(False, description="eine Hauptdatei samt ihren Begleitern (sonst nur ohne)")


class Verschieben(BaseModel):
    art: Literal["verschieben"]
    datei: str = Field(min_length=1, description="Pfad der Hauptdatei jetzt; ihre Begleiter ziehen mit")
    ordner: str = Field(min_length=1, description="Pfad des Zielordners; fehlt er, wird er angelegt")
    name: str | None = Field(None, min_length=1, description="neuer Name; die Begleiter ziehen ihren Namen nach")


Schritt = Annotated[Umhaengen | Verschieben | Weglegen, Field(discriminator="art")]


class Ordnung(BaseModel):
    konto: str = Field(min_length=1)
    titel: str = ""
    schritte: list[Schritt]


Befund = Literal["bereit", "erledigt", "konflikt", "ausgefuehrt", "fehler"]


class Stand(BaseModel):
    schritt: str
    befund: Befund
    grund: str = ""


def _text(s: Umhaengen | Verschieben | Weglegen) -> str:
    if isinstance(s, Umhaengen):
        return f"{s.datei} -> neben {s.haupt}"
    if isinstance(s, Verschieben):
        return f"{s.datei} -> {s.ordner}/{s.name or PurePosixPath(s.datei).name}"
    return f"{s.ziel} in den Papierkorb"


class OrdnenDienst:
    """Nutzt die Wege des Einspieldienstes (Konto, Pfade, Prüfsummen) und des Speicherdienstes."""

    def __init__(self, einspielen: EinspielDienst) -> None:
        self.e = einspielen
        self.speicher = einspielen.speicher

    async def pruefen(self, ordnung: Ordnung) -> list[Stand]:
        besitzer = await self.e.konto(ordnung.konto)
        aus = []
        for n, s in enumerate(ordnung.schritte):
            aus.append(await self._pruefen(besitzer, s, ordnung.schritte[:n]))
        return aus

    async def ausfuehren(self, ordnung: Ordnung, melden: Callable[[Stand], None] = lambda _s: None) -> list[Stand]:
        besitzer = await self.e.konto(ordnung.konto)
        aus = []
        for n, s in enumerate(ordnung.schritte):
            stand = await self._pruefen(besitzer, s, ordnung.schritte[:n])
            if stand.befund == "bereit":
                try:
                    await self._ausfuehren(besitzer, s)
                    stand = Stand(schritt=stand.schritt, befund="ausgefuehrt")
                except Exception as f:  # noqa: BLE001 - ein Schritt hält die übrigen nicht auf
                    stand = Stand(schritt=stand.schritt, befund="fehler", grund=f"{type(f).__name__}: {f}")
            aus.append(stand)
            melden(stand)
        return aus

    async def _pruefen(self, besitzer, s: Umhaengen | Verschieben | Weglegen, vorher: list) -> Stand:
        text = _text(s)
        if isinstance(s, Verschieben):
            return await self._verschieben_pruefen(besitzer, s, text)
        if isinstance(s, Umhaengen):
            haupt = await self.speicher.knoten_per_pfad(besitzer, s.haupt)
            if haupt is None or haupt["typ"] != "datei":
                return Stand(schritt=text, befund="konflikt", grund="Hauptdatei fehlt")
            namen = begleiter_regeln.namen(PurePosixPath(s.haupt).name, s.zusatz)
            ort = str(PurePosixPath(s.haupt).parent)
            for name in namen:
                da = await self.speicher.knoten_per_pfad(besitzer, f"{ort}/{name}")
                if da and await self._begleitet(da, haupt, s.rolle):
                    return Stand(schritt=text, befund="erledigt")
            datei = await self.speicher.knoten_per_pfad(besitzer, s.datei)
            if datei is None or datei["typ"] != "datei":
                return Stand(schritt=text, befund="konflikt", grund="Begleitdatei fehlt")
            async with self.e.pool.connection() as conn:
                repo = PostgresMetadataRepository(conn)
                vorhanden = await repo.begleiter_fuer_rolle(haupt["id"], s.rolle)
            if vorhanden and not vorhanden["geloescht"] and vorhanden["id"] != datei["id"]:
                return Stand(schritt=text, befund="konflikt", grund=f"{PurePosixPath(s.haupt).name} hat schon einen Begleiter {s.rolle}")
            belegt = [await self.speicher.knoten_per_pfad(besitzer, f"{ort}/{name}") for name in namen]
            if not any(k is None or k["id"] == datei["id"] for k in belegt):
                return Stand(schritt=text, befund="konflikt", grund=f"neben der Hauptdatei sind {' und '.join(namen)} vergeben")
            return Stand(schritt=text, befund="bereit")
        knoten = await self.speicher.knoten_per_pfad(besitzer, s.ziel)
        if knoten is None:
            return Stand(schritt=text, befund="erledigt", grund="liegt nicht (mehr) da")
        if s.sha256 and await self.e._aktueller_hash(knoten) != s.sha256:
            return Stand(schritt=text, befund="konflikt", grund="anderer Inhalt als im Plan")
        if knoten["typ"] == "datei" and not s.mit_begleitern:
            umgehaengt = {u.datei for u in vorher if isinstance(u, Umhaengen)}
            async with self.e.pool.connection() as conn:
                mit = await PostgresMetadataRepository(conn).begleiter_der_haupt(knoten["id"])
            bleiben = [b["name"] for b in mit if f"{PurePosixPath(s.ziel).parent}/{b['name']}" not in umgehaengt]
            if bleiben:
                return Stand(schritt=text, befund="konflikt", grund=f"Begleiter gingen mit: {', '.join(bleiben)}")
        return Stand(schritt=text, befund="bereit")

    async def _verschieben_pruefen(self, besitzer, s: Verschieben, text: str) -> Stand:
        """Erledigt, wenn die Datei fehlt und am Ziel eine gleichnamige liegt (ein früherer Lauf); bereit, wenn sie eine
        Hauptdatei ist und am Ziel jeder Name der Gruppe frei ist."""
        name = s.name or PurePosixPath(s.datei).name
        datei = await self.speicher.knoten_per_pfad(besitzer, s.datei)
        am_ziel = await self.speicher.knoten_per_pfad(besitzer, f"{s.ordner}/{name}")
        if datei is None:
            if am_ziel is not None:
                return Stand(schritt=text, befund="erledigt")
            return Stand(schritt=text, befund="konflikt", grund="Datei fehlt")
        if datei["typ"] != "datei":
            return Stand(schritt=text, befund="konflikt", grund="nur Dateien (samt Begleitern), keine Ordner")
        async with self.e.pool.connection() as conn:
            repo = PostgresMetadataRepository(conn)
            if await repo.begleiter_eintrag(datei["id"]):
                return Stand(schritt=text, befund="konflikt", grund="ist Begleiter; die Hauptdatei verschieben")
            mit = await repo.begleiter_der_haupt(datei["id"])
        namen = [name, *(begleiter_regeln.nachgezogen(datei["name"], name, b["name"]) or b["name"] for b in mit)]
        belegt = [n for n in namen if await self.speicher.knoten_per_pfad(besitzer, f"{s.ordner}/{n}") is not None]
        if belegt:
            return Stand(schritt=text, befund="konflikt", grund=f"am Ziel schon vorhanden: {', '.join(belegt)}")
        return Stand(schritt=text, befund="bereit")

    async def _begleitet(self, knoten, haupt, rolle: str) -> bool:
        async with self.e.pool.connection() as conn:
            eintrag = await PostgresMetadataRepository(conn).begleiter_eintrag(knoten["id"])
        return bool(eintrag) and eintrag["haupt_id"] == haupt["id"] and eintrag["rolle"] == rolle

    async def _ausfuehren(self, besitzer, s: Umhaengen | Verschieben | Weglegen) -> None:
        if isinstance(s, Verschieben):
            datei = await self.speicher.knoten_per_pfad(besitzer, s.datei)
            ordner = await self.e._ordner(besitzer, [t for t in s.ordner.split("/") if t])
            await self.speicher.umziehen(besitzer, datei["id"], ordner, s.name)
            return
        if isinstance(s, Umhaengen):
            haupt = await self.speicher.knoten_per_pfad(besitzer, s.haupt)
            datei = await self.speicher.knoten_per_pfad(besitzer, s.datei)
            await self.speicher.begleiter_anhaengen(besitzer, haupt["id"], datei["id"], s.rolle, s.zusatz, s.app)
            return
        knoten = await self.speicher.knoten_per_pfad(besitzer, s.ziel)
        await self.speicher.loeschen(besitzer, knoten["id"])

"""Der Plan zum Einspielen (eine JSON-Datei neben den Dateien, die er nennt) und die Befunde je Eintrag.

Ein Eintrag nennt das Ziel unter "Meine Dateien", die Datei im Ordner des Plans mit ihrer Prüfsumme, frühere Stände
(werden ältere Versionen, älteste zuerst), Inhaltstyp, erzeugende App, freie Felder und, für eine Begleitdatei, ihre
Hauptdatei mit Rolle und Zusatz. Der Name einer Begleitdatei ist der, den die Kellerwolke vergibt (Stamm der Hauptdatei
und Zusatz); der Plan nennt ihn ausdrücklich, damit die Vorschau zeigt, was entsteht.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

SHA256 = r"^[0-9a-f]{64}$"


class Stand(BaseModel):
    datei: str = Field(min_length=1, description="Pfad relativ zum Ordner des Plans")
    sha256: str = Field(pattern=SHA256)


class Begleitung(BaseModel):
    haupt: str = Field(min_length=1, description="Ziel der Hauptdatei (im Plan oder schon in der Kellerwolke)")
    rolle: str
    zusatz: str


class Eintrag(Stand):
    ziel: str = Field(min_length=1, description="Pfad unter Meine Dateien, etwa Apps/Stimmenausgabe/Stimmen/morf.wav")
    inhaltstyp: str | None = None
    app: str | None = Field(None, max_length=60, description="erzeugende App, wie sie die Kellerwolke anzeigt")
    felder: dict[str, Any] = Field(default_factory=dict)
    fruehere: list[Stand] = Field(default_factory=list, description="ältere Stände, älteste zuerst")
    ersetzt: str | None = Field(None, pattern=SHA256, description="liegt am Ziel genau dieser Stand, kommt der Eintrag "
                                                                  "als neue Version darüber (der alte bleibt Version)")
    begleitet: Begleitung | None = None


class Plan(BaseModel):
    konto: str = Field(min_length=1, description="Name des Kontos, dem die Dateien gehören")
    titel: str = ""
    eintraege: list[Eintrag]


# neu: wird angelegt; vorhanden: liegt schon genau so da; fortsetzen: ein früherer Abbruch, es fehlen spätere Stände
# oder die Gruppe; konflikt: am Ziel liegt etwas anderes, nichts geschieht; fehlt: die Datei im Plan fehlt oder hat eine
# andere Prüfsumme; eingespielt und fehler: nach dem Ausführen.
Befund = Literal["neu", "vorhanden", "fortsetzen", "konflikt", "fehlt", "eingespielt", "fehler"]


class Ergebnis(BaseModel):
    ziel: str
    befund: Befund
    grund: str = ""
    staende: int = 1

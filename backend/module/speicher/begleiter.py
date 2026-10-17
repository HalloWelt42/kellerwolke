"""Begleitdateien: Namen und Regeln an einer Stelle.

Ein Begleiter ist ein Ergebnis zu einer Hauptdatei (Transkript zu einem Ton, Sprachausgabe zu einem Text) und liegt im
selben Ordner, mit dem Stamm der Hauptdatei und einem Zusatz, den die App nennt: `Besprechung.wav` ->
`Besprechung.transkript.json`, `Besprechung.srt`. Ist dieser Name schon vergeben, trägt er den vollen Namen der
Hauptdatei: `Besprechung.wav.transkript.json`. Die Rolle (transkript, untertitel, sprache) ist die Kennung des Bezugs
und unabhängig vom Namen.

Regeln der Gruppe (Nutzer, 17.10.2026: "zusammengehörige dateien immer beieinander ablegen, so geht nix verloren"):
- Verschieben eines Mitglieds verschiebt die ganze Gruppe; aus der Gruppe lösen ist ein eigener Schritt.
- Umbenennen der Hauptdatei benennt die Begleiter mit (der Teil vor der Rolle folgt dem neuen Namen).
- Der Papierkorb der Hauptdatei nimmt die Begleiter mit; ein Begleiter allein geht allein.
- Wiederherstellen bringt Begleiter an die Seite ihrer Hauptdatei.
Die Durchsetzung steht im Speicherdienst, damit Oberfläche, Apps und WebDAV gleich handeln.
"""

from __future__ import annotations

import re

ROLLE = re.compile(r"^[a-z][a-z_]{0,39}$")          # wie die Art einer Herkunft
ZUSATZ = re.compile(r"^(\.[a-z0-9][a-z0-9_-]{0,19}){1,3}$")   # .srt, .transkript.json, .sprache.mp3
NAME_MAX = 255


class GruppeKonflikt(ValueError):
    """Ein Begleiter kann nicht mitziehen, weil sein Name am Ziel schon vergeben ist; dann geschieht gar nichts."""


def rolle_pruefen(rolle: str) -> str:
    if not ROLLE.match(rolle or ""):
        raise ValueError("Rolle: Kleinbuchstaben und _, höchstens 40 Zeichen (etwa transkript, untertitel, sprache)")
    return rolle


def zusatz_pruefen(zusatz: str) -> str:
    zusatz = (zusatz or "").lower()
    if not ZUSATZ.match(zusatz) or len(zusatz) > 40:
        raise ValueError("Zusatz: ein bis drei Teile mit Punkt vorn, Kleinbuchstaben und Ziffern (etwa .srt, "
                         ".transkript.json, .sprache.mp3)")
    return zusatz


def stamm(name: str) -> str:
    """Name ohne die letzte Endung; ohne Endung (oder nur mit Punkt vorn) der ganze Name."""
    vorne, punkt, _ = name.rpartition(".")
    return vorne if punkt and vorne else name


def namen(haupt_name: str, zusatz: str) -> list[str]:
    """Mögliche Namen eines Begleiters neben der Hauptdatei, der bevorzugte zuerst."""
    kurz = f"{stamm(haupt_name)}{zusatz}"
    lang = f"{haupt_name}{zusatz}"
    return [n for n in dict.fromkeys((kurz, lang)) if len(n) <= NAME_MAX]


def nachgezogen(alt_haupt: str, neu_haupt: str, begleiter_name: str) -> str | None:
    """Name eines Begleiters, nachdem die Hauptdatei von alt_haupt in neu_haupt umbenannt wurde; None, wenn sein Name
    nicht dem Muster folgt (dann bleibt er). Der volle Name wird vor dem Stamm geprüft (längerer Anfang zuerst)."""
    for alt, neu in ((alt_haupt, neu_haupt), (stamm(alt_haupt), stamm(neu_haupt))):
        if begleiter_name.startswith(alt + "."):
            ergebnis = neu + begleiter_name[len(alt):]
            return ergebnis if len(ergebnis) <= NAME_MAX else None
    return None

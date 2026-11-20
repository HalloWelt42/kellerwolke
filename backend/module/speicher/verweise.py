"""Verweise: Regeln an einer Stelle (KW-10, Entscheid des Nutzers 20.11.2026).

Ein Verweis ist ein eigener Eintrag (Knotenart `verweis`), der auf eine Datei desselben Kontos zeigt, statt sie zu
kopieren: jede Datei gibt es genau einmal. Die Telegram-Ablage etwa legt Bilder in die Bildablage und daneben in ihrem
Chat-Ordner nur einen Verweis darauf.

- Ziel ist immer das Original, eine Datei. Zeigt ein neuer Verweis auf einen Verweis, gilt dessen Original (Ketten
  entstehen so nie). Ordner, externe Quellen und verwaiste Verweise sind kein Ziel.
- Lesen folgt dem Ziel: Inhalt, Versionen, Vorschau und Größe sind die des Originals. Schreiben geht nur am Original;
  ein Verweis hat keine eigenen Versionen und belegt keinen Platz. Name, Ort und Felder hat er selbst.
- Apps legen Verweise nur dort an, wo sie schreiben dürfen, und nur auf Dateien, die sie lesen dürfen.
- Verweis löschen nimmt nur den Verweis. Das Original nimmt alle lebenden Verweise darauf mit in den Papierkorb (wie
  seine Begleiter) und holt sie beim Wiederherstellen an ihren Ort zurück; endgültig löschen entfernt sie mit. Vorher
  zeigt die Oberfläche die Folgen mit Pfaden (`loeschfolgen`).
- Fehlt das Ziel (endgültig gelöscht) oder liegt es im Papierkorb, ist der Verweis verwaist: er bleibt sichtbar,
  liefert keinen Inhalt und lässt sich nur noch entfernen.
- Die Volltextsuche zählt Verweise nicht doppelt, WebDAV zeigt sie nur lesend.
Die Durchsetzung steht im Speicherdienst, damit Oberfläche, Apps und WebDAV gleich handeln.
"""

from __future__ import annotations

TYP = "verweis"


class VerweisUngueltig(ValueError):
    """Das Ziel taugt nicht für einen Verweis (keine Datei, verwaist, fremd, im Papierkorb)."""


class VerweisNurLesbar(Exception):
    """Auf einen Verweis wird nicht geschrieben; geschrieben wird am Original."""


def ohne_doppel(treffer: list[dict]) -> list[dict]:
    """Suchtreffer ohne Verweise, deren Original selbst trifft oder schon über einen anderen Verweis da ist; die
    Reihenfolge bleibt. So zählt jede Datei einmal, ein Verweis bleibt nur, wenn allein sein Name traf."""
    originale = {t["id"] for t in treffer if t["typ"] != TYP}
    gesehen: set = set()
    aus = []
    for t in treffer:
        if t["typ"] == TYP and t.get("ziel_id") is not None:
            if t["ziel_id"] in originale or t["ziel_id"] in gesehen:
                continue
            gesehen.add(t["ziel_id"])
        aus.append(t)
    return aus

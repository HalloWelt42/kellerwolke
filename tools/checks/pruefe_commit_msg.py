#!/usr/bin/env python3
"""Pruefung der Commit-Nachricht (KI-Erwaehnung, Marken, Typografie, Umlaute)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import regeln


def main():
    if len(sys.argv) < 2:
        print("commit-msg: keine Nachrichtendatei uebergeben")
        return 1
    text = Path(sys.argv[1]).read_text(encoding="utf-8")
    rumpf = "\n".join(z for z in text.split("\n") if not z.startswith("#"))

    fehler = []
    if not rumpf.strip():
        fehler.append((0, "Leer", "Commit-Nachricht ist leer"))
    # Als Prosa pruefen (echte Umlaute erwuenscht).
    for zeile, art, detail in regeln.pruefe_datei("commit-nachricht.md", rumpf):
        fehler.append((zeile, art, detail))

    if fehler:
        print("\nBARRIERE: Commit-Nachricht abgelehnt\n")
        for zeile, art, detail in fehler:
            print("  [%s] Zeile %d -> %s" % (art, zeile, detail))
        print()
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

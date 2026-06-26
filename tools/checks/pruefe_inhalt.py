#!/usr/bin/env python3
"""Inhaltspruefung fuer Hooks und CI.

Aufruf:
  pruefe_inhalt.py --staged   # nur die fuer den Commit vorgemerkten Dateien
  pruefe_inhalt.py --alle     # alle versionierten Dateien (CI-Backstop)
  pruefe_inhalt.py DATEI ...  # einzelne Dateien (Test)
"""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import regeln


def git_ausgabe(args):
    return subprocess.run(["git"] + args, capture_output=True, text=True).stdout


def staged_dateien():
    out = git_ausgabe(["diff", "--cached", "--name-only", "--diff-filter=ACM"])
    return [z for z in out.splitlines() if z.strip()]


def alle_dateien():
    out = git_ausgabe(["ls-files"])
    return [z for z in out.splitlines() if z.strip()]


def ist_binaer(roh):
    return b"\x00" in roh[:8000]


def lies_bytes(pfad, aus_index):
    if aus_index:
        ergebnis = subprocess.run(["git", "show", ":" + pfad], capture_output=True)
        if ergebnis.returncode != 0:
            return None
        return ergebnis.stdout
    p = Path(pfad)
    if not p.exists():
        return None
    return p.read_bytes()


def main():
    args = sys.argv[1:]
    modus = "--staged"
    explizit = []
    for a in args:
        if a in ("--staged", "--alle"):
            modus = a
        else:
            explizit.append(a)

    if explizit:
        dateien = explizit
        aus_index = False
    else:
        dateien = staged_dateien() if modus == "--staged" else alle_dateien()
        aus_index = (modus == "--staged")

    fehler = []
    for pfad in dateien:
        pv = regeln.pfad_verstoss(pfad)
        if pv:
            fehler.append((pfad, 0, "Pfad", pv))
        roh = lies_bytes(pfad, aus_index)
        if roh is None or ist_binaer(roh):
            continue
        try:
            text = roh.decode("utf-8")
        except UnicodeDecodeError:
            fehler.append((pfad, 0, "Kodierung", "Datei ist nicht UTF-8"))
            continue
        for zeile, art, detail in regeln.pruefe_datei(pfad, text):
            fehler.append((pfad, zeile, art, detail))

    if fehler:
        print("\nBARRIERE: Inhaltspruefung fehlgeschlagen\n")
        for pfad, zeile, art, detail in fehler:
            ort = "%s:%d" % (pfad, zeile) if zeile else pfad
            print("  [%s] %s -> %s" % (art, ort, detail))
        print("\nBitte beheben. Notfalls (nicht empfohlen) mit --no-verify, "
              "der CI-Backstop blockt es trotzdem.\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

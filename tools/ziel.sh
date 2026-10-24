#!/usr/bin/env bash
# Ziel des Ausrollens aus deploy/ausrollen.toml (eine Wahrheit für die Skripte und das Handbuch), zum Einbinden mit
# ". tools/ziel.sh": setzt PI, WURZEL und ADRESSE. KELLERWOLKE_PI und KELLERWOLKE_PI_WURZEL gehen vor.
ziel_wert() {
  python3 -c 'import sys, tomllib; print(tomllib.load(open(sys.argv[1], "rb"))[sys.argv[2]])' \
    "$(dirname "${BASH_SOURCE[0]}")/../deploy/ausrollen.toml" "$1"
}
PI="${KELLERWOLKE_PI:-$(ziel_wert rechner)}"
WURZEL="${KELLERWOLKE_PI_WURZEL:-$(ziel_wert wurzel)}"
ADRESSE="$(ziel_wert adresse)"

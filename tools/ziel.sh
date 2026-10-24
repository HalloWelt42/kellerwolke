#!/usr/bin/env bash
# Ziel des Ausrollens aus der privaten Wahrheit des Hauses (handbuch ziel kellerwolke), zum Einbinden mit
# ". tools/ziel.sh": setzt PI, WURZEL, ADRESSE und NAMEN. KELLERWOLKE_PI, KELLERWOLKE_PI_WURZEL, KELLERWOLKE_ADRESSE und
# KELLERWOLKE_NAMEN aus der Umgebung gehen vor; ohne sie und ohne das Werkzeug handbuch bricht es mit klarer Meldung ab.
ziel_wert() {
  if [ -n "${2:-}" ]; then printf '%s' "$2"; return; fi
  command -v handbuch >/dev/null 2>&1 || { echo "Ziel fehlt: $1 (Werkzeug handbuch oder Umgebung)" >&2; exit 1; }
  handbuch ziel kellerwolke "$1" || { echo "Ziel fehlt: handbuch ziel kellerwolke $1" >&2; exit 1; }
}
PI="$(ziel_wert rechner "${KELLERWOLKE_PI:-}")"
WURZEL="$(ziel_wert wurzel "${KELLERWOLKE_PI_WURZEL:-}")"
ADRESSE="$(ziel_wert adresse "${KELLERWOLKE_ADRESSE:-}")"
NAMEN="$(ziel_wert namen "${KELLERWOLKE_NAMEN:-}")"

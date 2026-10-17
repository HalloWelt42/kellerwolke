#!/usr/bin/env bash
# Ausrollen auf den Pi (vom Mac): erst gepusht, dann Sicherung, neuen Stand holen, dort bauen und prüfen.
set -euo pipefail
PI="${KELLERWOLKE_PI:-pi@192.168.178.49}"
WURZEL="${KELLERWOLKE_PI_WURZEL:-/mnt/data/kellerwolke}"
cd "$(dirname "$0")/.."
[ -z "$(git status --porcelain)" ] || { echo "Erst committen: der Pi holt nur gepushte Stände."; exit 1; }
git fetch -q origin
[ "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)" ] || { echo "Erst pushen (main ist nicht auf origin)."; exit 1; }
ssh -o BatchMode=yes "$PI" "'$WURZEL/tools/pi/sichern.sh'"
ssh -o BatchMode=yes "$PI" "cd '$WURZEL' && git pull --ff-only -q"
ssh -o BatchMode=yes "$PI" "'$WURZEL/tools/pi/ausrollen.sh'"

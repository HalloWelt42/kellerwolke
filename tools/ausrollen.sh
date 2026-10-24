#!/usr/bin/env bash
# Ausrollen auf den Pi (vom Mac): erst gepusht, dann Sicherung, neuen Stand holen, dort bauen und prüfen. Ziel und
# Adresse kommen aus der privaten Wahrheit (tools/ziel.sh); am Ende muss die Adresse die ausgerollte Fassung melden.
set -euo pipefail
# >>> handbuch: vorher Seite, Einrichtungsskript, Probelauf und Bau des Handbuchs (eingesetzt von "handbuch einbinden")
handbuch_befehl="$(command -v handbuch || true)"
[ -n "$handbuch_befehl" ] || handbuch_befehl="$HOME/.local/bin/handbuch"
if [ ! -x "$handbuch_befehl" ]; then
  echo "Abbruch: das Werkzeug handbuch fehlt (Handbuch, Grundlage Mac)" >&2
  exit 1
fi
"$handbuch_befehl" freigabe "$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)" || {
  echo "Abbruch: das Handbuch ist nicht in Ordnung, nichts ausgerollt" >&2
  exit 1
}
# <<< handbuch
cd "$(dirname "$0")/.."
. tools/ziel.sh
[ -z "$(git status --porcelain)" ] || { echo "Erst committen: der Pi holt nur gepushte Stände."; exit 1; }
git fetch -q origin
[ "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)" ] || { echo "Erst pushen (main ist nicht auf origin)."; exit 1; }
ssh -o BatchMode=yes "$PI" "'$WURZEL/tools/pi/sichern.sh'"
ssh -o BatchMode=yes "$PI" "cd '$WURZEL' && git pull --ff-only -q"
ssh -o BatchMode=yes "$PI" "'$WURZEL/tools/pi/ausrollen.sh'"
SOLL="$(tr -d ' \t\n\r' < VERSION)"
IST="$(curl -s -m 10 --cacert "$(mkcert -CAROOT)/rootCA.pem" "$ADRESSE/api/health" \
  | python3 -c 'import sys, json; print(json.load(sys.stdin)["version"])' 2>/dev/null || true)"
[ "$IST" = "$SOLL" ] || { echo "Abbruch: $ADRESSE meldet ${IST:-nichts} statt $SOLL (Ziel prüfen: handbuch ziel kellerwolke)"; exit 1; }
echo "Ausgerollt: $ADRESSE meldet $IST"

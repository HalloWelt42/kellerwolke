#!/usr/bin/env bash
# Blattzertifikat für die Kellerwolke aus der Hausstelle (mkcert) ausstellen und auf den Pi bringen.
# Der Schlüssel der Hausstelle bleibt auf diesem Mac; auf den Pi gehen nur Blattzertifikat, Blattschlüssel, das
# öffentliche Zertifikat der Hausstelle und sein Fingerabdruck. Dieselbe Hausstelle wie bei der Kiste: ein Telefon,
# das der Kiste vertraut, vertraut auch der Kellerwolke.
#
# Nutzung: tools/zertifikat.sh [--pruefen]
#   --pruefen  nur die Restlaufzeit auf dem Pi prüfen; Status 1, wenn unter 60 Tagen oder kein Zertifikat
set -euo pipefail
PI="${KELLERWOLKE_PI:-pi@192.168.178.49}"
ZIEL="${KELLERWOLKE_PI_WURZEL:-/mnt/data/kellerwolke}/data/zertifikate"
NAMEN="${KELLERWOLKE_NAMEN:-192.168.178.49 raspberrypi-3.fritz.box raspberrypi-3 kellerwolke.fritz.box kellerwolke.local kellerwolke}"
SCHWELLE_S=$((60 * 86400))

if [ "${1:-}" = "--pruefen" ]; then
  ssh -o BatchMode=yes "$PI" "test -f '$ZIEL/kellerwolke.pem' && openssl x509 -in '$ZIEL/kellerwolke.pem' -noout -checkend $SCHWELLE_S" >/dev/null 2>&1
  exit $?
fi

command -v mkcert >/dev/null 2>&1 || { echo "mkcert fehlt auf diesem Mac."; exit 1; }
HAUSSTELLE="$(mkcert -CAROOT)/rootCA.pem"
[ -f "$HAUSSTELLE" ] || { echo "Die Hausstelle fehlt: $HAUSSTELLE"; exit 1; }

ARBEIT="$(mktemp -d)"
trap 'rm -rf "$ARBEIT"' EXIT
# shellcheck disable=SC2086 - die Namen sind eine Liste
(cd "$ARBEIT" && mkcert -cert-file kellerwolke.pem -key-file kellerwolke-schluessel.pem $NAMEN >/dev/null 2>&1)
openssl x509 -in "$HAUSSTELLE" -noout -fingerprint -sha256 | sed 's/^.*=//' > "$ARBEIT/fingerabdruck.txt"
cp "$HAUSSTELLE" "$ARBEIT/rootCA.pem"

ssh -o BatchMode=yes "$PI" "mkdir -p '$ZIEL'"
scp -q "$ARBEIT/kellerwolke.pem" "$ARBEIT/kellerwolke-schluessel.pem" "$ARBEIT/rootCA.pem" "$ARBEIT/fingerabdruck.txt" "$PI:$ZIEL/"
ssh -o BatchMode=yes "$PI" "chmod 644 '$ZIEL/kellerwolke.pem' '$ZIEL/rootCA.pem' '$ZIEL/fingerabdruck.txt' && chmod 600 '$ZIEL/kellerwolke-schluessel.pem'"
ABLAUF="$(openssl x509 -in "$ARBEIT/kellerwolke.pem" -noout -enddate | sed 's/^.*=//')"
echo "Zertifikat ausgestellt und übertragen, gültig bis: $ABLAUF"

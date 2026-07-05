#!/usr/bin/env bash
# Verwaltung von Kellerwolke - immer MIT Befehl aufrufen (kein blosses Starten).
# Die Startlogik liegt in start.sh (dieselbe, die auch der systemd-Dienst nutzt);
# setup.sh ist der bequeme Einstieg mit allen Befehlen:
#   ./setup.sh start | stop | restart | status | update | logs [n] | db-stop
# "update" zieht den aktuellen Stand von origin und startet neu.
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/start.sh" "$@"

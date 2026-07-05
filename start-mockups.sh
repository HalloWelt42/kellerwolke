#!/usr/bin/env bash
# Mockup-Viewer steuern:  ./start-mockups.sh [start|stop|restart|status] [port]
#
# Startet einen statischen Server (Projektwurzel) im Hintergrund - die Konsole
# bleibt frei. Es läuft immer höchstens EINE Instanz; PID und Port merkt sich
# das Skript unter .run/, daher brauchen stop/status/restart keinen Port.
# Die Mockups laden Schrift und Icons aus frontend/node_modules, deshalb wird
# die Projektwurzel ausgeliefert.
#
# Beispiele:  ./start-mockups.sh            (Port 8477)
#             ./start-mockups.sh 8478        (anderer Port)
#             ./start-mockups.sh status
#             ./start-mockups.sh stop
set -uo pipefail

HIER="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN="$HIER/.run"; mkdir -p "$RUN"
PIDF="$RUN/mockups.pid"
PORTF="$RUN/mockups.port"
LOG="$RUN/mockups.log"

lebt() { [ -f "$PIDF" ] && kill -0 "$(cat "$PIDF" 2>/dev/null)" 2>/dev/null; }

stop() {
  if [ -f "$PIDF" ]; then kill "$(cat "$PIDF" 2>/dev/null)" 2>/dev/null; fi
  rm -f "$PIDF" "$PORTF"
}

start() {
  stop
  nohup python3 -m http.server "$PORT" --directory "$HIER" > "$LOG" 2>&1 &
  echo "$!" > "$PIDF"; echo "$PORT" > "$PORTF"
  sleep 0.3
  if lebt; then
    echo "Mockup-Viewer läuft auf Port $PORT (PID $(cat "$PIDF"))"
    echo "  Viewer:  http://localhost:$PORT/mockups/viewer.html"
    echo "  Galerie: http://localhost:$PORT/mockups/index.html"
  else
    echo "Start fehlgeschlagen - Log: $LOG"; tail -n 3 "$LOG" 2>/dev/null; exit 1
  fi
}

# Argumente in beliebiger Reihenfolge: ein Kommando und/oder eine Portzahl.
CMD=""; PORT_ARG=""
for arg in "$@"; do
  case "$arg" in
    start|stop|restart|status) CMD="$arg" ;;
    *[!0-9]*|'') echo "Nutzung: $0 [start|stop|restart|status] [port]"; exit 1 ;;
    *) PORT_ARG="$arg" ;;
  esac
done
CMD="${CMD:-start}"

# Port: explizit > gemerkter Port der laufenden Instanz > Standard.
if [ -n "$PORT_ARG" ]; then PORT="$PORT_ARG"
elif [ -f "$PORTF" ]; then PORT="$(cat "$PORTF")"
else PORT="${MOCKUP_PORT:-8477}"; fi

case "$CMD" in
  start)   start ;;
  restart) start ;;
  stop)    stop; echo "Mockup-Viewer gestoppt" ;;
  status)
    if lebt; then echo "Mockup-Viewer: läuft auf Port $PORT (PID $(cat "$PIDF"))"
    else echo "Mockup-Viewer: aus"; fi ;;
esac

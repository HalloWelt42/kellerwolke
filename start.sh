#!/usr/bin/env bash
# Steuerung der gesamten Anwendung: ./start.sh [start|stop|restart|status]
# Bringt die Datenbank (Docker), das Backend (uvicorn) und das Frontend (vite) hoch.
set -uo pipefail

HIER="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN="$HIER/.run"; mkdir -p "$RUN"
ENVFILE="$HIER/.env"

bash "$HIER/tools/setup-env.sh"

# Konfiguration: gesetzte Umgebungsvariable > .env > Standardwert.
envget() {
  # Umgebungsvariable per eval lesen - portabel; ${!key} (indirekte Expansion)
  # bricht auf bash 5.2 mit "set -u" ab.
  local key="$1" def="$2" val=""
  eval "val=\${$key-}"
  if [ -z "$val" ] && [ -f "$ENVFILE" ]; then
    val="$(sed -n "s/^${key}=//p" "$ENVFILE" | head -1)"
    val="${val%\"}"; val="${val#\"}"; val="${val%\'}"; val="${val#\'}"
  fi
  printf '%s' "${val:-$def}"
}

BIND="$(envget KELLERWOLKE_BIND 127.0.0.1)"
BPORT="$(envget KELLERWOLKE_BACKEND_PORT 8460)"
FPORT="$(envget KELLERWOLKE_FRONTEND_PORT 5200)"

listener() { lsof -nP -iTCP:"$1" -sTCP:LISTEN -t 2>/dev/null; }
compose() { docker compose --env-file "$ENVFILE" "$@"; }

db_start() {
  compose up -d db
  printf "Warte auf Datenbank "
  for _ in $(seq 1 30); do
    if compose exec -T db pg_isready -q 2>/dev/null; then echo " bereit"; return 0; fi
    printf "."; sleep 1
  done
  echo " (Zeitueberschreitung)"; return 1
}

backend_start() {
  cd "$HIER/backend"
  if [ ! -d .venv ]; then
    python3 -m venv .venv
    ./.venv/bin/pip install -q --upgrade pip
    ./.venv/bin/pip install -q -r requirements.txt
  fi
  nohup ./.venv/bin/uvicorn app.main:app --host "$BIND" --port "$BPORT" --log-level warning > "$RUN/backend.log" 2>&1 &
  echo $! > "$RUN/backend.pid"
}

frontend_start() {
  cd "$HIER/frontend"
  [ -d node_modules ] || npm install
  nohup npm run dev -- --port "$FPORT" --strictPort > "$RUN/frontend.log" 2>&1 &
  echo $! > "$RUN/frontend.pid"
}

stop_all() {
  for f in backend frontend; do
    if [ -f "$RUN/$f.pid" ]; then kill "$(cat "$RUN/$f.pid")" 2>/dev/null; rm -f "$RUN/$f.pid"; fi
  done
  for p in "$BPORT" "$FPORT"; do
    pids="$(listener "$p")"; [ -n "$pids" ] && kill -9 $pids 2>/dev/null
  done
}

status() {
  for pair in "Backend $BPORT" "Frontend $FPORT"; do
    set -- $pair
    if [ -n "$(listener "$2")" ]; then echo "$1 ($2): laeuft"; else echo "$1 ($2): aus"; fi
  done
  if compose ps db 2>/dev/null | grep -q "Up\|running"; then echo "Datenbank: laeuft"; else echo "Datenbank: aus"; fi
}

case "${1:-start}" in
  start)
    stop_all; sleep 1
    db_start || { echo "Datenbank nicht erreichbar, Abbruch"; exit 1; }
    backend_start; frontend_start
    echo "Kellerwolke gestartet -> Frontend http://localhost:$FPORT   API http://localhost:$BPORT/api/health"
    echo "Logs: $RUN/backend.log , $RUN/frontend.log"
    ;;
  stop)
    stop_all
    echo "Kellerwolke gestoppt (Datenbank laeuft weiter; './start.sh db-stop' beendet sie)"
    ;;
  db-stop)
    compose down
    echo "Datenbank gestoppt"
    ;;
  restart)
    stop_all; sleep 1; db_start; backend_start; frontend_start
    echo "Kellerwolke neu gestartet -> http://localhost:$FPORT"
    ;;
  status)
    status
    ;;
  *)
    echo "Nutzung: $0 [start|stop|restart|status|db-stop]"; exit 1
    ;;
esac

#!/usr/bin/env bash
# Steuerung der gesamten Anwendung - IMMER mit Befehl aufrufen (kein blosses Starten):
#   ./setup.sh start|stop|restart|status|update|logs|db-stop   (start.sh ist dasselbe)
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

hochfahren() {
  stop_all; sleep 1
  db_start || { echo "Datenbank nicht erreichbar, Abbruch"; exit 1; }
  backend_start; frontend_start
  echo "Kellerwolke gestartet -> Frontend http://localhost:$FPORT   API http://localhost:$BPORT/api/health"
  echo "Logs: $RUN/backend.log , $RUN/frontend.log   (oder ./setup.sh logs)"
}

# Aktuellen Stand von origin ziehen und neu starten. Bewusst hart auf den
# Serverstand (git reset --hard): so blockiert eine lokale Aenderung - etwa eine
# ZIP-Installation - den Wechsel nicht. .env und die Datenbank liegen ausserhalb
# von Git und bleiben unberuehrt.
update() {
  cd "$HIER" || exit 1
  git rev-parse --git-dir >/dev/null 2>&1 || { echo "Kein Git-Repository - Update nicht moeglich."; exit 1; }
  local zweig; zweig="$(git rev-parse --abbrev-ref HEAD)"
  echo "Hole aktuellen Stand von origin/$zweig ..."
  git fetch --prune origin || { echo "git fetch fehlgeschlagen"; exit 1; }
  if [ -n "$(git status --porcelain)" ]; then
    echo "Hinweis: lokale Aenderungen werden fuer den Deploy-Stand verworfen:"
    git status --short
  fi
  git reset --hard "origin/$zweig" || { echo "git reset fehlgeschlagen"; exit 1; }
  echo "Neuer Stand: $(git rev-parse --short HEAD)  (Version $(cat VERSION 2>/dev/null))"
  echo "Abhaengigkeiten aktualisieren ..."
  if [ -d "$HIER/backend/.venv" ]; then
    ( cd "$HIER/backend" && ./.venv/bin/pip install -q -r requirements.txt ) || echo "  (Backend-Pakete uebersprungen)"
  fi
  ( cd "$HIER/frontend" && npm install --no-audit --no-fund >/dev/null 2>&1 ) || echo "  (Frontend-Pakete uebersprungen)"
  echo "Neustart ..."
  hochfahren
  echo "Update fertig."
}

zeige_logs() {
  local n="${1:-40}"
  echo "== Backend (letzte $n Zeilen) =="; tail -n "$n" "$RUN/backend.log" 2>/dev/null || echo "  (kein Log)"
  echo; echo "== Frontend (letzte $n Zeilen) =="; tail -n "$n" "$RUN/frontend.log" 2>/dev/null || echo "  (kein Log)"
}

nutzung() {
  cat <<TEXT
Kellerwolke - Nutzung: $0 <befehl>
  start      Datenbank, Backend und Frontend starten
  stop       Backend und Frontend stoppen (Datenbank laeuft weiter)
  restart    alles neu starten
  status     Laufzustand anzeigen
  update     aktuellen Stand von origin ziehen, Pakete pruefen, neu starten
  logs [n]   letzte n Log-Zeilen (Standard 40) von Backend und Frontend
  db-stop    Datenbank (Docker) stoppen
TEXT
}

# Kein Standardbefehl mehr: ohne Befehl wird die Nutzung gezeigt (kein Autostart).
case "${1:-}" in
  start)   hochfahren ;;
  stop)    stop_all; echo "Kellerwolke gestoppt (Datenbank laeuft weiter; './setup.sh db-stop' beendet sie)" ;;
  restart) hochfahren ;;
  status)  status ;;
  update)  update ;;
  logs)    zeige_logs "${2:-40}" ;;
  db-stop) compose down; echo "Datenbank gestoppt" ;;
  ""|-h|--help|help) nutzung; exit 1 ;;
  *)       echo "Unbekannter Befehl: $1"; echo; nutzung; exit 1 ;;
esac

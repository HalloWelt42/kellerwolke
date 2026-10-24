#!/usr/bin/env bash
# Einrichten der Kellerwolke. Schritte und Proben der Neueinrichtung stehen in docs/handbuch.md.
#
#   ./einrichten.sh                                       im Klon auf dem Zielgerät: .env (nur wenn keine da ist; Ports
#                                                         aus dem Ordner), Python-Umgebung, Oberfläche bauen, Datenbank;
#                                                         mit systemd (Pi) dazu die Dienste (tools/systemd-einrichten.sh)
#   ./einrichten.sh --probe --ziel DIR --port-versatz N   Probelauf des Handbuchs: dieselben Schritte in DIR, Ports des
#                                                         Betriebs (handbuch ziel kellerwolke) plus N, Wegwerfgeheimnisse,
#                                                         Dateipool in DIR, Backend als Prozess statt Dienst
#   ./einrichten.sh --probe --ziel DIR --abbauen          Backend beenden, Datenbank samt Volume entfernen
set -euo pipefail
HIER="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROBE_WARTEN_S=120

umgebung_bauen() {
  cd "$1/backend"
  [ -x .venv/bin/python ] || python3 -m venv .venv
  .venv/bin/pip install -q --upgrade pip
  .venv/bin/pip install -q -r requirements.txt
  cd "$1/frontend"
  npm install --no-audit --no-fund --silent
  npm run build --silent >/dev/null
}

datenbank_starten() {
  cd "$1"
  docker compose --env-file .env up -d db
  for _ in $(seq 1 60); do
    if docker compose --env-file .env exec -T db pg_isready -q 2>/dev/null; then return 0; fi
    sleep 1
  done
  echo "Die Datenbank wird nicht bereit" >&2
  return 1
}

einrichten() {
  bash "$HIER/tools/setup-env.sh"
  umgebung_bauen "$HIER"
  datenbank_starten "$HIER"
  if command -v systemctl >/dev/null 2>&1; then
    "$HIER/tools/systemd-einrichten.sh"
    sudo systemctl start kellerwolke.target
    echo "Kellerwolke eingerichtet und gestartet (sudo systemctl status kellerwolke.target)"
  else
    echo "Kellerwolke eingerichtet. Start: ./setup.sh start"
  fi
}

# Port des Betriebs aus der privaten Wahrheit (handbuch ziel), damit er nur dort steht; der Probelauf ruft das Skript
# mit demselben verbund.toml auf, das er selbst liest
ziel_port() {
  handbuch ziel kellerwolke "port:$1"
}

probe_aufbauen() {
  local ziel="$1" versatz="$2" backend db
  backend=$(( $(ziel_port backend) + versatz ))
  db=$(( $(ziel_port datenbank) + versatz ))
  cd "$ziel"
  mkdir -p data/objects .run
  (
    umask 077
    sed -e "s|^COMPOSE_PROJECT_NAME=.*|COMPOSE_PROJECT_NAME=\"${COMPOSE_PROJECT_NAME:?}\"|" \
        -e "s|^KELLERWOLKE_BACKEND_PORT=.*|KELLERWOLKE_BACKEND_PORT=\"$backend\"|" \
        -e "s|^KELLERWOLKE_DB_PORT=.*|KELLERWOLKE_DB_PORT=\"$db\"|" \
        -e "s|^KELLERWOLKE_DB_PASS=.*|KELLERWOLKE_DB_PASS=\"$(openssl rand -hex 12)\"|" \
        -e "s|^KELLERWOLKE_APP_SECRET=.*|KELLERWOLKE_APP_SECRET=\"$(openssl rand -hex 24)\"|" \
        .env.muster > .env
    echo "KELLERWOLKE_OBJEKT_PFAD=\"$ziel/data/objects\"" >> .env
  )
  umgebung_bauen "$ziel"
  datenbank_starten "$ziel"
  cd "$ziel/backend"
  nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port "$backend" --log-level warning \
    > "$ziel/.run/backend.log" 2>&1 &
  echo $! > "$ziel/.run/backend.pid"
  local ende=$(( $(date +%s) + PROBE_WARTEN_S ))
  while [ "$(date +%s)" -lt "$ende" ]; do
    if curl -sf "http://127.0.0.1:$backend/api/health" >/dev/null; then
      echo "ANTWORTET http://127.0.0.1:$backend/api/health"
      return 0
    fi
    sleep 1
  done
  echo "Das Backend antwortet nach $PROBE_WARTEN_S s nicht" >&2
  tail -n 40 "$ziel/.run/backend.log" >&2 || true
  return 1
}

probe_abbauen() {
  cd "$1"
  if [ -f .run/backend.pid ]; then
    kill "$(cat .run/backend.pid)" 2>/dev/null || true
    rm -f .run/backend.pid
  fi
  if [ -f .env ]; then
    docker compose --env-file .env down --volumes --remove-orphans
  fi
}

probe=0; abbauen=0; ziel=""; versatz=""
while [ $# -gt 0 ]; do
  case "$1" in
    --probe) probe=1 ;;
    --abbauen) abbauen=1 ;;
    --ziel) ziel="${2:?--ziel braucht einen Ordner}"; shift ;;
    --port-versatz) versatz="${2:?--port-versatz braucht eine Zahl}"; shift ;;
    *) echo "unbekannte Angabe: $1" >&2; exit 2 ;;
  esac
  shift
done

if [ "$probe" = 0 ]; then
  einrichten
elif [ -z "$ziel" ] || [ ! -d "$ziel" ]; then
  echo "--probe braucht --ziel mit einem vorhandenen Ordner" >&2; exit 2
elif [ "$abbauen" = 1 ]; then
  probe_abbauen "$(cd "$ziel" && pwd)"
else
  probe_aufbauen "$(cd "$ziel" && pwd)" "${versatz:?--port-versatz fehlt}"
fi

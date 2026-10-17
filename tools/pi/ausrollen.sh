#!/usr/bin/env bash
# Auf dem Pi, nach dem Holen des neuen Stands: Abhängigkeiten, Oberfläche bauen, Dienste neu starten, prüfen.
# Aufgerufen von tools/ausrollen.sh auf dem Mac.
set -euo pipefail
WURZEL="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$WURZEL"
wert() { sed -n "s/^$1=//p" .env | tr -d '"' | head -1; }
BPORT="$(wert KELLERWOLKE_BACKEND_PORT)"; FPORT="$(wert KELLERWOLKE_FRONTEND_PORT)"; TPORT="$(wert KELLERWOLKE_TLS_PORT)"

backend/.venv/bin/pip install -q -r backend/requirements.txt
(cd frontend && npm install --no-audit --no-fund --silent && npm run build --silent >/dev/null)
sudo systemctl restart kellerwolke-backend
sudo systemctl restart kellerwolke-web

SOLL="$(cat VERSION)"
for _ in $(seq 1 60); do
  IST="$(curl -s -m 2 "http://127.0.0.1:${BPORT}/api/health" | python3 -c 'import sys,json; print(json.load(sys.stdin)["version"])' 2>/dev/null || true)"
  [ "$IST" = "$SOLL" ] && break
  sleep 1
done
[ "$IST" = "$SOLL" ] || { echo "Backend meldet ${IST:-nichts} statt $SOLL"; exit 1; }
echo "Backend: $IST"
pruefe() { curl -s -f -o /dev/null "$@" || { echo "Fehlgeschlagen: ${*: -1}"; exit 1; }; }
for _ in $(seq 1 20); do curl -s -f -o /dev/null "http://127.0.0.1:${FPORT}/" && break; sleep 1; done
pruefe "http://127.0.0.1:${FPORT}/" && echo "Oberfläche ohne TLS: ok"
pruefe "http://127.0.0.1:${FPORT}/api/health" && echo "Schnittstelle über vorne: ok"
if [ -n "$TPORT" ] && [ -f data/zertifikate/rootCA.pem ]; then
  pruefe --cacert data/zertifikate/rootCA.pem "https://$(wert KELLERWOLKE_HAUPTADRESSE):${TPORT}/api/health" && echo "Mit TLS: ok"
fi
PROJEKT="$(wert COMPOSE_PROJECT_NAME)"
docker exec "${PROJEKT:-kellerwolke}-db-1" sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At -c "select count(*) from knoten"' | sed 's/^/Knoten: /'

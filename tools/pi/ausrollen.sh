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
# Datenbank auf den Stand des Compose bringen: nur bei einer Änderung neu angelegt (etwa die Bindung an 127.0.0.1, HELF-169)
docker compose --env-file "$WURZEL/.env" up -d db 2>&1 | grep -v "^ *Container .* Running$" || true
for _ in $(seq 1 30); do docker compose --env-file "$WURZEL/.env" exec -T db pg_isready -q 2>/dev/null && break; sleep 1; done
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
VORNE="https://$(wert KELLERWOLKE_HAUPTADRESSE):${TPORT}"
for _ in $(seq 1 20); do curl -s -f -o /dev/null --cacert data/zertifikate/rootCA.pem "$VORNE/" && break; sleep 1; done
pruefe --cacert data/zertifikate/rootCA.pem "$VORNE/" && echo "Oberfläche mit TLS: ok"
pruefe --cacert data/zertifikate/rootCA.pem "$VORNE/api/health" && echo "Schnittstelle über vorne: ok"
# Ohne TLS gibt es nur noch die Umleitung (KW-4): 308 auf dieselbe Stelle mit TLS, nie die Oberfläche selbst
UMLEITUNG="$(curl -s -o /dev/null -w '%{http_code} %{redirect_url}' "http://127.0.0.1:${FPORT}/medien?x=1")"
[ "$UMLEITUNG" = "308 https://127.0.0.1:${TPORT}/medien?x=1" ] || { echo "Ohne TLS: $UMLEITUNG statt Umleitung"; exit 1; }
echo "Ohne TLS nur Umleitung: ok"
PROJEKT="$(wert COMPOSE_PROJECT_NAME)"
docker exec "${PROJEKT:-kellerwolke}-db-1" sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At -c "select count(*) from knoten"' | sed 's/^/Knoten: /'

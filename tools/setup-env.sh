#!/usr/bin/env bash
# Erzeugt eine pro Klon eindeutige .env (falls keine da ist) und aktiviert die Git-Hooks.
# Projektname und Host-Ports werden ueber cksum aus dem absoluten Pfad abgeleitet,
# damit mehrere Klone kollisionsfrei nebeneinander laufen. Secrets sind zufaellig.
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$ROOT/.env"
VORLAGE="$ROOT/.env.muster"

# Git-Hooks aktivieren (idempotent, harte Barrieren von Anfang an).
if [ -d "$ROOT/.git" ]; then
  git -C "$ROOT" config core.hooksPath .githooks || true
fi

[ -f "$ENV_FILE" ] && exit 0
[ -f "$VORLAGE" ] || { echo "setup-env: Vorlage .env.muster fehlt" >&2; exit 1; }

ID="$(printf '%s' "$ROOT" | cksum | awk '{print $1}')"
BASE="$((20000 + ID % 20000))"
NAME="kellerwolke-$(printf '%06d' "$((ID % 1000000))")"
P_BACKEND="$BASE"; P_FRONT="$((BASE + 1))"; P_DB="$((BASE + 2))"

rand() {
  n="${1:-16}"
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex "$n"
  elif [ -r /dev/urandom ]; then
    head -c "$n" /dev/urandom | od -An -tx1 | tr -d ' \n'
  else
    echo "setup-env: weder openssl noch /dev/urandom verfuegbar - kann keine sicheren Geheimnisse erzeugen" >&2
    exit 1
  fi
}
SECRET="$(rand 24)"; DBPASS="$(rand 12)"

sed \
  -e "s|^COMPOSE_PROJECT_NAME=.*|COMPOSE_PROJECT_NAME=\"$NAME\"|" \
  -e "s|^KELLERWOLKE_BACKEND_PORT=.*|KELLERWOLKE_BACKEND_PORT=\"$P_BACKEND\"|" \
  -e "s|^KELLERWOLKE_FRONTEND_PORT=.*|KELLERWOLKE_FRONTEND_PORT=\"$P_FRONT\"|" \
  -e "s|^KELLERWOLKE_DB_PORT=.*|KELLERWOLKE_DB_PORT=\"$P_DB\"|" \
  -e "s|^KELLERWOLKE_DB_PASS=.*|KELLERWOLKE_DB_PASS=\"$DBPASS\"|" \
  -e "s|^KELLERWOLKE_APP_SECRET=.*|KELLERWOLKE_APP_SECRET=\"$SECRET\"|" \
  "$VORLAGE" > "$ENV_FILE"

echo "setup-env: eindeutige .env erzeugt (Projekt: $NAME)"
echo "  Backend  http://localhost:$P_BACKEND     Frontend http://localhost:$P_FRONT     DB localhost:$P_DB"

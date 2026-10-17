#!/usr/bin/env bash
# Auf dem Pi: Datenbank sichern (vor jedem Ausrollen). Legt eine geprüfte, gepackte Sicherung neben das Projekt.
set -euo pipefail
WURZEL="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$WURZEL"
PROJEKT="$(sed -n 's/^COMPOSE_PROJECT_NAME=//p' .env | tr -d '"' | head -1)"
ZIEL="$(dirname "$WURZEL")/kellerwolke_db_backup_$(date +%Y%m%d-%H%M%S).sql.gz"
docker exec "${PROJEKT:-kellerwolke}-db-1" sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' | gzip > "$ZIEL"
gzip -t "$ZIEL"
echo "Sicherung: $ZIEL ($(du -h "$ZIEL" | cut -f1))"

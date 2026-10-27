#!/usr/bin/env bash
# Auf dem Pi: Datenbank sichern nach der Sicherungsregel des Hauses.
#
#   tools/pi/sichern.sh                  regelmäßig (cron, Zeile in docs/handbuch.md): fällig, sobald die jüngste
#                                        Sicherung SICHERUNG_ABSTAND_TAGE Tage alt ist
#   tools/pi/sichern.sh --vor-ausrollen  von tools/ausrollen.sh: fällig, sobald die jüngste Sicherung
#                                        SICHERUNG_VOR_AUSROLLEN_AB_STUNDEN Stunden alt ist
#
# Ist eine Sicherung fällig, entsteht ein gepackter Auszug; gleicht er inhaltlich der jüngsten Sicherung, wird er
# verworfen (nie ohne Änderung). Danach bleiben bei jedem Lauf die SICHERUNG_BEHALTEN neuesten Sicherungen.
# Die Vorgaben stehen nur hier; Umgebung und .env der App gehen vor. Die Sicherungen liegen in sicherungen/ des Klons.
# Dort liegt sonst nichts (das Werkzeug Sicherungen am Mac holt die neuesten Einträge); Teildateien beginnen mit Punkt.
set -euo pipefail
# Auszüge enthalten Konten und Schlüssel: Ordner und Dateien nur für den Besitzer
umask 077
WURZEL="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$WURZEL"

ORDNER="$WURZEL/sicherungen"
VORSILBE="kellerwolke_db_backup_"
ENDUNG=".sql.gz"
TEILDATEI=""
trap '[ -z "$TEILDATEI" ] || rm -f "$TEILDATEI"' EXIT

# Wert aus der Umgebung, sonst aus der .env der App, sonst die Vorgabe
einstellung() {
  local wert="${!1:-}"
  if [ -z "$wert" ] && [ -f .env ]; then
    wert="$(sed -n "s/^$1=//p" .env | tr -d "\"'" | sed -n 1p)"
  fi
  printf '%s' "${wert:-$2}"
}

# Einstellung als ganze Zahl ab 1, sonst Abbruch
zahl() {
  local wert
  wert="$(einstellung "$1" "$2")"
  if ! [[ "$wert" =~ ^[0-9]+$ ]] || [ $((10#$wert)) -lt 1 ]; then
    echo "Abbruch: $1 muss eine ganze Zahl ab 1 sein (ist: '$wert')" >&2
    exit 2
  fi
  printf '%s' $((10#$wert))
}

# Sicherungen dieser App, die neueste zuerst (nach Änderungszeit); nur Dateien nach dem eigenen Muster
sicherungen_neueste_zuerst() {
  local staende=()
  shopt -s nullglob
  staende=("$ORDNER/$VORSILBE"*"$ENDUNG")
  shopt -u nullglob
  if [ ${#staende[@]} -gt 0 ]; then ls -1t -- "${staende[@]}"; fi
}

# Alter einer Datei in Sekunden nach ihrer Änderungszeit
alter_s() {
  echo $(( $(date +%s) - $(date -r "$1" +%s) ))
}

# Inhalt eines gepackten Auszugs ohne die Zeilen \restrict und \unrestrict: pg_dump schreibt dort bei jedem Lauf einen
# neuen Zufallsschlüssel hinein, gleiche Daten ergäben sonst nie gleiche Auszüge
inhalt() {
  gzip -dc "$1" | grep -v -E '^\\(un)?restrict ' || true
}

gleicher_inhalt() {
  cmp -s <(inhalt "$1") <(inhalt "$2")
}

# Neuer Auszug, wenn sich die Datenbank seit der jüngsten Sicherung ($1, leer: es gibt keine) geändert hat
sichern() {
  local juengste="$1" stempel name
  stempel="$(date +%Y%m%d-%H%M%S)"
  name="$VORSILBE$stempel$ENDUNG"
  TEILDATEI="$ORDNER/.$name.teil"
  docker exec "$CONTAINER" sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' | gzip -n > "$TEILDATEI"
  gzip -t "$TEILDATEI"
  if [ -n "$juengste" ] && gleicher_inhalt "$TEILDATEI" "$juengste"; then
    rm -f "$TEILDATEI"
    TEILDATEI=""
    echo "Keine neue Sicherung: die Datenbank ist seit $(basename "$juengste") unverändert"
    return
  fi
  # Änderungszeit ist der Beginn des Auszugs auf die Minute (JJJJMMTThhmm aus dem Stempel): ein Aufruf zur selben
  # Zeit eine Woche später ist dann sicher fällig, auch wenn der Auszug ein paar Sekunden gedauert hat
  touch -t "${stempel:0:8}${stempel:9:4}" "$TEILDATEI"
  mv "$TEILDATEI" "$ORDNER/$name"
  TEILDATEI=""
  echo "Sicherung: $ORDNER/$name ($(du -h "$ORDNER/$name" | cut -f1))"
}

# Höchstens SICHERUNG_BEHALTEN Sicherungen, die neuesten bleiben
aufraeumen() {
  local alt
  sicherungen_neueste_zuerst | tail -n +$((SICHERUNG_BEHALTEN + 1)) | while IFS= read -r alt; do
    rm -f -- "$alt"
    echo "Aufgeräumt: $(basename "$alt")"
  done
}

SICHERUNG_ABSTAND_TAGE="$(zahl SICHERUNG_ABSTAND_TAGE 7)"
SICHERUNG_VOR_AUSROLLEN_AB_STUNDEN="$(zahl SICHERUNG_VOR_AUSROLLEN_AB_STUNDEN 24)"
SICHERUNG_BEHALTEN="$(zahl SICHERUNG_BEHALTEN 3)"
CONTAINER="$(einstellung COMPOSE_PROJECT_NAME kellerwolke)-db-1"

# Ab diesem Alter der jüngsten Sicherung ist eine neue fällig
case "${1:-}" in
  "") GRENZE_S=$((SICHERUNG_ABSTAND_TAGE * 86400)); GRENZE="$SICHERUNG_ABSTAND_TAGE Tage" ;;
  --vor-ausrollen)
    GRENZE_S=$((SICHERUNG_VOR_AUSROLLEN_AB_STUNDEN * 3600)); GRENZE="$SICHERUNG_VOR_AUSROLLEN_AB_STUNDEN Stunden" ;;
  *) echo "Unbekannte Angabe: $1 (ohne Angabe regelmäßig, sonst --vor-ausrollen)" >&2; exit 2 ;;
esac

mkdir -p "$ORDNER"
JUENGSTE="$(sicherungen_neueste_zuerst | sed -n 1p)"
if [ -n "$JUENGSTE" ] && [ "$(alter_s "$JUENGSTE")" -lt "$GRENZE_S" ]; then
  echo "Keine neue Sicherung: die jüngste ($(basename "$JUENGSTE")) ist jünger als $GRENZE"
else
  sichern "$JUENGSTE"
fi
aufraeumen

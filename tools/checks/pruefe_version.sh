#!/usr/bin/env bash
# Erzwingt: jeder Push hat eine hoehere VERSION als der Remote-Stand.
set -euo pipefail

DATEI="VERSION"
[ -f "$DATEI" ] || { echo "BARRIERE: VERSION-Datei fehlt"; exit 1; }

lokal="$(tr -d ' \t\n\r' < "$DATEI")"
if ! printf '%s' "$lokal" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+$'; then
  echo "BARRIERE: VERSION '$lokal' ist kein gueltiges Semver (x.y.z)"
  exit 1
fi

groesser() {
  # Erfolg (0), wenn $1 strikt groesser als $2 ist.
  local IFS=.
  local a=($1) b=($2)
  local i
  for i in 0 1 2; do
    if [ "${a[$i]}" -gt "${b[$i]}" ]; then return 0; fi
    if [ "${a[$i]}" -lt "${b[$i]}" ]; then return 1; fi
  done
  return 1
}

git fetch -q origin 2>/dev/null || true
remote_ref="origin/main"

if ! git rev-parse --verify -q "$remote_ref" >/dev/null; then
  echo "Repo-Schutz: kein $remote_ref vorhanden - erster Push, Versionspruefung uebersprungen."
  exit 0
fi

remote="$(git show "$remote_ref:$DATEI" 2>/dev/null | tr -d ' \t\n\r' || true)"
if [ -z "$remote" ]; then
  echo "Repo-Schutz: keine Remote-VERSION gefunden - akzeptiert."
  exit 0
fi

if ! groesser "$lokal" "$remote"; then
  echo "BARRIERE: VERSION muss hochgezaehlt werden (Remote: $remote, lokal: $lokal)"
  echo "          Patch +0.0.1 je Aenderung, Feature +0.1.0."
  exit 1
fi

echo "Repo-Schutz: VERSION $remote -> $lokal in Ordnung."
exit 0

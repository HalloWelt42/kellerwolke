#!/usr/bin/env bash
# Stellt sicher, dass nur die erlaubte Git-Identitaet committet/pusht.
set -euo pipefail

ERLAUBT_NAME="HalloWelt42"
ERLAUBT_MAIL="my@jobmagnetix.de"

modus="${1:---config}"
fehler=0

pruefe() {
  local name="$1" mail="$2" quelle="$3"
  if [ "$name" != "$ERLAUBT_NAME" ] || [ "$mail" != "$ERLAUBT_MAIL" ]; then
    echo "BARRIERE: falsche Git-Identitaet ($quelle): $name <$mail>"
    echo "          erlaubt ist nur: $ERLAUBT_NAME <$ERLAUBT_MAIL>"
    fehler=1
  fi
}

case "$modus" in
  --config)
    pruefe "$(git config user.name || true)" "$(git config user.email || true)" "git config"
    ;;
  --head)
    pruefe "$(git log -1 --format='%an')" "$(git log -1 --format='%ae')" "Autor HEAD"
    pruefe "$(git log -1 --format='%cn')" "$(git log -1 --format='%ce')" "Committer HEAD"
    ;;
  --bereich)
    bereich="${2:-}"
    [ -n "$bereich" ] || { echo "Bereich fehlt"; exit 2; }
    while IFS='|' read -r an ae cn ce; do
      [ -n "$an" ] || continue
      pruefe "$an" "$ae" "Autor ($bereich)"
      pruefe "$cn" "$ce" "Committer ($bereich)"
    done < <(git log --format='%an|%ae|%cn|%ce' "$bereich")
    ;;
  *)
    echo "Aufruf: pruefe_identitaet.sh [--config|--head|--bereich <range>]"
    exit 2
    ;;
esac

exit $fehler

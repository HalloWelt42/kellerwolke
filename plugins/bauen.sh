#!/usr/bin/env bash
# Paketiert jedes Plugin-Paket plugins/<id>/ nach plugins/<id>/<id>.zip
# (Layout: plugin.json + backend/ + frontend/, genau wie der Upload es erwartet).
set -euo pipefail
cd "$(dirname "$0")"
for d in */; do
  id="${d%/}"
  [ -f "$id/plugin.json" ] || continue
  rm -f "$id/$id.zip"
  ( cd "$id" && zip -r -q "$id.zip" plugin.json backend frontend -x '*/__pycache__/*' )
  echo "gebaut: plugins/$id/$id.zip"
done

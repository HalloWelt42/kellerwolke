#!/usr/bin/env bash
# Richtet Kellerwolke als systemd-Dienst ein - mit echter Ueberwachung.
#
# Warum nicht mehr ein einziger oneshot-Dienst, der ./setup.sh start ruft:
# setup.sh legt die Prozesse per nohup daneben und kehrt zurueck. systemd sah den
# uvicorn-Prozess dadurch NIE. Als der Kernel das Backend wegen Speichermangels
# abschoss, blieb es tot liegen - niemand hat es neu gestartet. Genau das darf
# nicht passieren.
#
# Deshalb jetzt: jeder Prozess laeuft im VORDERGRUND unter seiner eigenen Unit,
# systemd sieht ihn sterben und startet ihn neu (Restart=always).
#
#   kellerwolke-db.service        Datenbank (Docker) - einmalig hochfahren
#   kellerwolke-backend.service   uvicorn, ueberwacht + Neustart
#   kellerwolke-frontend.service  vite,    ueberwacht + Neustart
#   kellerwolke.target            klammert alles zusammen
#
# Aufruf (auf dem Zielgeraet):  ./tools/systemd-einrichten.sh
# Danach:                       sudo systemctl {status,start,stop,restart} kellerwolke.target
set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)"
ENVFILE="$DIR/.env"

if ! command -v systemctl >/dev/null 2>&1; then
  echo "systemd (systemctl) nicht gefunden - dieser Schritt ist nur fuer das"
  echo "Linux-Zielgeraet (Pi) gedacht. Auf dem Entwickler-Mac entfaellt er;"
  echo "dort wird die Anwendung mit ./setup.sh gestartet."
  exit 0
fi

BENUTZER="${SUDO_USER:-$(id -un)}"

# Werte wie in setup.sh lesen: Umgebung > .env > Standard.
envget() {
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

if [ ! -x "$DIR/backend/.venv/bin/uvicorn" ]; then
  echo "Backend-Umgebung fehlt ($DIR/backend/.venv)."
  echo "Bitte einmal './setup.sh start' laufen lassen, dann hier erneut."
  exit 1
fi

schreibe() { printf '%s\n' "$2" | sudo tee "/etc/systemd/system/$1" >/dev/null; }

schreibe "kellerwolke-db.service" "$(cat <<EOF
[Unit]
Description=Kellerwolke - Datenbank (Docker)
After=docker.service network-online.target
Requires=docker.service
PartOf=kellerwolke.target

[Service]
Type=oneshot
RemainAfterExit=yes
User=${BENUTZER}
WorkingDirectory=${DIR}
ExecStart=/usr/bin/docker compose --env-file ${ENVFILE} up -d db
ExecStop=/usr/bin/docker compose --env-file ${ENVFILE} stop db
TimeoutStartSec=300

[Install]
WantedBy=kellerwolke.target
EOF
)"

# Der eigentliche Fallschirm: uvicorn im Vordergrund, systemd startet neu.
# Auch nach einem Abschuss durch den Kernel (OOM) - genau der Fall von neulich.
schreibe "kellerwolke-backend.service" "$(cat <<EOF
[Unit]
Description=Kellerwolke - Backend (uvicorn)
After=kellerwolke-db.service network-online.target
Requires=kellerwolke-db.service
PartOf=kellerwolke.target

[Service]
Type=simple
User=${BENUTZER}
WorkingDirectory=${DIR}/backend
EnvironmentFile=-${ENVFILE}
ExecStart=${DIR}/backend/.venv/bin/uvicorn app.main:app --host ${BIND} --port ${BPORT} --log-level warning
Restart=always
RestartSec=5
# Nach einem Absturz nicht endlos im Kreis starten, aber grosszuegig genug,
# dass ein einzelner Ausrutscher folgenlos bleibt.
StartLimitIntervalSec=300
StartLimitBurst=10
# Bei Speichermangel zuerst hier aufraeumen statt die halbe Maschine zu treffen.
OOMPolicy=continue

[Install]
WantedBy=kellerwolke.target
EOF
)"

schreibe "kellerwolke-frontend.service" "$(cat <<EOF
[Unit]
Description=Kellerwolke - Frontend (vite)
After=kellerwolke-backend.service
PartOf=kellerwolke.target

[Service]
Type=simple
User=${BENUTZER}
WorkingDirectory=${DIR}/frontend
EnvironmentFile=-${ENVFILE}
ExecStart=/usr/bin/npm run dev -- --port ${FPORT} --strictPort
Restart=always
RestartSec=5

[Install]
WantedBy=kellerwolke.target
EOF
)"

schreibe "kellerwolke.target" "$(cat <<EOF
[Unit]
Description=Kellerwolke - eigene Dateiwolke
Wants=kellerwolke-db.service kellerwolke-backend.service kellerwolke-frontend.service
After=kellerwolke-db.service

[Install]
WantedBy=multi-user.target
EOF
)"

# Der alte Einzeldienst wuerde sonst parallel dieselben Ports belegen.
if systemctl list-unit-files | grep -q "^kellerwolke.service"; then
  echo "Alten Einzeldienst kellerwolke.service abschalten ..."
  sudo systemctl disable --now kellerwolke.service 2>/dev/null || true
  sudo rm -f /etc/systemd/system/kellerwolke.service
fi

sudo systemctl daemon-reload
sudo systemctl enable kellerwolke.target kellerwolke-db.service \
  kellerwolke-backend.service kellerwolke-frontend.service >/dev/null

echo "Eingerichtet (Benutzer=${BENUTZER}, Verzeichnis=${DIR})."
echo "  Starten : sudo systemctl start kellerwolke.target"
echo "  Status  : systemctl status kellerwolke-backend"
echo "  Logs    : journalctl -u kellerwolke-backend -f"
echo
echo "Das Backend wird jetzt ueberwacht: stirbt es (auch durch den OOM-Killer),"
echo "startet systemd es nach ${RestartSec:-5} Sekunden von selbst neu."

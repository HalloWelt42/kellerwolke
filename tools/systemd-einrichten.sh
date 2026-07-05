#!/usr/bin/env bash
# Richtet Kellerwolke als systemd-Dienst ein, damit die Anwendung nach einem
# Neustart automatisch wieder hochkommt (Reboot-Persistenz auf dem Pi).
#
# Der Dienst ruft schlicht ./setup.sh start / stop - die bewaehrte Startlogik
# (Datenbank via Docker, Backend per uvicorn, Frontend per vite) bleibt die
# einzige Quelle der Wahrheit. Pfade und Benutzer werden aus der Umgebung
# ermittelt, nichts ist fest verdrahtet.
#
# Aufruf (auf dem Zielgeraet):  ./tools/systemd-einrichten.sh
# Danach steuerbar mit:         sudo systemctl {status,start,stop,restart} kellerwolke
set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)"
DIENST="kellerwolke"
ZIEL="/etc/systemd/system/${DIENST}.service"

if ! command -v systemctl >/dev/null 2>&1; then
  echo "systemd (systemctl) nicht gefunden - dieser Schritt ist nur fuer das"
  echo "Linux-Zielgeraet (Pi) gedacht. Auf dem Entwickler-Mac entfaellt er;"
  echo "dort wird die Anwendung mit ./setup.sh gestartet."
  exit 0
fi

# Benutzer ermitteln: bei sudo der urspruengliche Aufrufer, sonst der aktuelle.
BENUTZER="${SUDO_USER:-$(id -un)}"

EINHEIT="$(cat <<EOF
[Unit]
Description=Kellerwolke - eigene Dateiwolke
After=docker.service network-online.target
Wants=docker.service network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
# setup.sh legt die Prozesse per nohup im Hintergrund ab und kehrt zurueck;
# KillMode=process laesst systemd nur den Startbefehl verwalten, nicht die
# Kindprozesse mitreissen. Gestoppt wird sauber ueber ExecStop.
KillMode=process
User=${BENUTZER}
WorkingDirectory=${DIR}
ExecStart=${DIR}/setup.sh start
ExecStop=${DIR}/setup.sh stop
TimeoutStartSec=600

[Install]
WantedBy=multi-user.target
EOF
)"

echo "Schreibe ${ZIEL} (Benutzer=${BENUTZER}, Verzeichnis=${DIR}) ..."
printf '%s\n' "$EINHEIT" | sudo tee "$ZIEL" >/dev/null
sudo systemctl daemon-reload
sudo systemctl enable "$DIENST"
echo "Eingerichtet. Starten mit:  sudo systemctl start ${DIENST}"
echo "Status ansehen mit:         systemctl status ${DIENST}"

# Plugins

Hier liegen unsere Plugin-Pakete - je Plugin ein Unterordner mit dem Namen des
Plugins. Jedes Paket enthält den Quellcode (plugin.json + backend/ + frontend/)
und das gebaute, installierbare ZIP.

Das ZIP wird per `./bauen.sh` aus dem jeweiligen Quellpaket erzeugt. Installiert
wird ein Plugin über die Oberfläche (Verwaltung -> Apps -> App hochladen).

Aufbau der Pakete und die Plugin-Entwicklung sind in `../docs/PLUGINS.md`
beschrieben.

# Wurzel aller Backend-Plugins. Jedes Plugin ist ein Unterpaket plugins/<id>/
# mit plugin.json (Manifest) und einer register(kontext)-Funktion. Der Kern
# entdeckt sie ueber app/plugins.py - er importiert sie NIE direkt.

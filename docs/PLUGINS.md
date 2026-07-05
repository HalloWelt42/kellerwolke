# Plugins bauen

Diese Anleitung beschreibt haarklein, wie ein Plugin (in der Oberfläche "App"
genannt) für Kellerwolke gebaut, getestet, paketiert und installiert wird.
Stand: Kern v0.44.0. Sie ist die verbindliche Referenz für jedes weitere Plugin.

## 1. Was ein Plugin ist

Ein Plugin erweitert Kellerwolke um eine eigene **Ansicht** (erscheint in der
App-Leiste unter dem Suchfeld) und optional um **Datei-Fähigkeiten** (zeigt im
Normalmodus z.B. eine Vorschau oder Vollansicht für bestimmte Dateitypen).

Grundsätze:

- Ein Plugin besteht aus **zwei gepaarten Ordnern** - einem Backend- und einem
  Frontend-Teil - die über dieselbe `id` zusammengehören.
- Jedes Plugin bringt **eigene Datenbank-Tabellen** mit, isoliert in einem
  eigenen Postgres-Schema `plugin_<id>`. Es fasst keine Kern-Tabellen schreibend an.
- Der **Kern importiert nie direkt** ein Plugin. Der einzige Weg hinein führt
  über das Manifest und den Lader.
- Ein defektes Plugin **deaktiviert nur sich selbst** (es wird als `defekt`
  markiert) - der Kern startet immer weiter.

## 2. Verzeichnisstruktur

Ein Plugin mit der `id` `meinplugin` belegt genau diese beiden Orte:

```
backend/plugins/meinplugin/
    plugin.json              # Manifest (Pflicht)
    __init__.py              # leer, macht den Ordner zum Python-Paket (nur bei Backend-Teil)
    api.py                   # register(kontext) -> baut den Router (nur bei Backend-Teil)
    dienst.py                # eigene Logik (frei benennbar)
    schema/
        001_meinplugin.sql   # eigene Tabellen (optional, aufsteigend nummeriert)

frontend/src/plugins/meinplugin/
    plugin.ts                # Default-Export: das AppPlugin-Objekt (Pflicht)
    Ansicht.svelte           # die Hauptansicht
    ...                      # weitere Komponenten/Helfer frei
```

Wichtig: Der **Ordnername MUSS exakt der `id` entsprechen**. Stimmt das nicht
überein, lehnt der Lader das Plugin ab.

## 3. Das Manifest `plugin.json`

Jedes Feld zählt. Beispiel:

```json
{
  "id": "meinplugin",
  "name": "Mein Plugin",
  "version": "1.0.0",
  "kategorie": "ansicht-app",
  "icon": "fa-solid fa-flask",
  "backend_entry": "api:register",
  "frontend_entry": "plugin.ts",
  "kern_min": "0.44.0",
  "daten_loeschen_bei_deinstall": "fragen"
}
```

| Feld | Bedeutung | Regeln |
|------|-----------|--------|
| `id` | Eindeutiger Bezeichner, zugleich Ordnername und Schema-Suffix | Muster `^[a-z][a-z0-9_]{1,30}$` - Kleinbuchstaben, Ziffern, Unterstrich; beginnt mit Buchstabe |
| `name` | Anzeigename in der Oberfläche | Echte Umlaute erlaubt |
| `version` | Plugin-Version | Semver-artig `major.minor.patch` |
| `kategorie` | Art des Plugins | Aktuell nur `ansicht-app` |
| `icon` | Symbol in App-Leiste und Verwaltung | Font-Awesome-Klasse, z.B. `fa-solid fa-images` |
| `backend_entry` | Modul und Funktion des Backend-Teils, Format `modul:funktion` | Standard `api:register`. **Leerstring `""`** = reines Frontend-Plugin, kein Backend |
| `frontend_entry` | Einstiegsdatei des Frontend-Teils | i.d.R. `plugin.ts` |
| `kern_min` | Mindest-Kernversion | Ist der Kern älter, wird das Plugin nicht geladen |
| `daten_loeschen_bei_deinstall` | Hinweis fürs Deinstallieren | `fragen` (Nutzer entscheidet), informativ |

## 4. Backend-Teil

Der Backend-Teil ist optional. Setze `backend_entry` auf `""`, wenn dein Plugin
rein im Frontend lebt (dann entfällt alles in diesem Abschnitt).

### 4.1 Einstiegspunkt `register(kontext)`

`backend_entry` zeigt auf eine Funktion (Standard `api:register` =
`api.py` -> `register`). Sie bekommt einen `PluginKontext` und liefert eine
`PluginBeschreibung` zurück:

```python
# backend/plugins/meinplugin/api.py
from fastapi import APIRouter, HTTPException, Request
from app.plugin_api import PluginBeschreibung, PluginKontext
from .dienst import MeinDienst


def register(kontext: PluginKontext) -> PluginBeschreibung:
    dienst = MeinDienst(kontext)
    router = APIRouter(prefix="/api/v1/plugins/meinplugin", tags=["meinplugin"])

    async def benutzer_aus_token(request: Request):
        # Token kommt per Query (?t=...) ODER Header x-kellerwolke-sitzung.
        # Query-Token ist noetig, weil <img src> keine Header setzen kann.
        token = request.query_params.get("t") or request.headers.get("x-kellerwolke-sitzung", "")
        benutzer = await kontext.auth.sitzung_pruefen(token)
        if not benutzer:
            raise HTTPException(status_code=401, detail="Anmeldung erforderlich")
        return benutzer

    @router.get("/etwas/{knoten_id}")
    async def etwas(knoten_id: str, request: Request):
        benutzer = await benutzer_aus_token(request)
        return await dienst.etwas(benutzer["id"], knoten_id)

    return PluginBeschreibung(router=router)
```

Konventionen:

- **Router-Prefix immer** `/api/v1/plugins/<id>`. So kollidieren Plugins nie mit
  Kern-Routen oder untereinander.
- **Eigene Authentifizierung** über `kontext.auth.sitzung_pruefen(token)`. Es
  gibt keine automatische Absicherung der Plugin-Routen - jede Route prüft selbst.
- Fehlerfälle als `HTTPException` (401 nicht angemeldet, 404 nicht gefunden,
  415 nicht darstellbar usw.).

### 4.2 Der `PluginKontext`

Das einzige Tor zum Kern. Greife ausschließlich hierüber zu:

| Feld / Eigenschaft | Zweck |
|--------------------|-------|
| `kontext.manifest` | Das geladene Manifest |
| `kontext.plugin_pfad` | `Path` zum Backend-Ordner des Plugins |
| `kontext.speicher` | `SpeicherDienst` - Dateien lesen, Knoten prüfen (mit Eigentümerprüfung) |
| `kontext.auth` | `AuthDienst` - Sitzung prüfen |
| `kontext.pool` | Postgres-Pool (psycopg) für eigene Abfragen |
| `kontext.aktueller_benutzer` | FastAPI-Dependency für angemeldete Nutzer |
| `kontext.aktueller_admin` | FastAPI-Dependency für Admins |
| `kontext.schema` | Name des eigenen Schemas, `plugin_<id>` |

Dateizugriff läuft **immer** über `kontext.speicher`, damit die
Eigentümerprüfung des Kerns greift. Nützliche Methoden:

- `await kontext.speicher.knoten_des_nutzers(benutzer_id, knoten_id)` - liefert
  den Knoten nur, wenn er dem Nutzer gehört, sonst `None`.
- `await kontext.speicher.datei_lesen(benutzer_id, knoten_id)` - Bytes der Datei.
- `await kontext.speicher.dateien_nach_endung(benutzer_id, ["%.jpg", "%.png"])` -
  alle Dateien des Nutzers im ganzen Baum mit vollem Ordnerpfad.

### 4.3 Eigene Tabellen (Schema)

Lege deine SQL-Dateien unter `schema/` ab, aufsteigend nummeriert
(`001_...sql`, `002_...sql`). Sie werden **nur bei aktivem Plugin** ausgeführt,
in einem eigenen Schema `plugin_<id>` (der `search_path` ist beim Anwenden auf
`plugin_<id>, public` gesetzt). Regeln:

- Tabellen ohne Schema-Präfix anlegen (`CREATE TABLE IF NOT EXISTS einstellung
  (...)`) - sie landen automatisch in `plugin_<id>`.
- Auf Kern-Tabellen mit `public.`-Präfix verweisen, z.B.
  `REFERENCES public.benutzer(id) ON DELETE CASCADE`.
- Immer idempotent schreiben (`IF NOT EXISTS`, `ADD COLUMN IF NOT EXISTS`), die
  Dateien werden bei jedem Start erneut angewandt.

```sql
-- backend/plugins/meinplugin/schema/001_meinplugin.sql
CREATE TABLE IF NOT EXISTS einstellung (
    benutzer_id uuid PRIMARY KEY REFERENCES public.benutzer(id) ON DELETE CASCADE,
    wert        text DEFAULT '',
    geaendert_am timestamptz NOT NULL DEFAULT now()
);
```

## 5. Frontend-Teil

### 5.1 Einstieg `plugin.ts`

Default-Export ist ein `AppPlugin`-Objekt:

```ts
// frontend/src/plugins/meinplugin/plugin.ts
import type { AppPlugin } from "../typen";
import Ansicht from "./Ansicht.svelte";

const plugin: AppPlugin = {
  id: "meinplugin",
  label: "Mein Plugin",
  icon: "fa-solid fa-flask",
  reihenfolge: 50,
  bereiche: ["dateien", "favoriten", "geteilt"],
  ansicht: Ansicht,
};

export default plugin;
```

Felder von `AppPlugin`:

| Feld | Bedeutung |
|------|-----------|
| `id` | Muss zur Manifest-`id` passen |
| `label` | Text in der App-Leiste |
| `icon` | Font-Awesome-Klasse |
| `reihenfolge?` | Sortierung in der App-Leiste (kleiner = weiter vorn) |
| `bereiche?` | In welchen Bereichen die App sinnvoll ist (`dateien`, `favoriten`, `geteilt`, ...); fehlt = überall |
| `ansicht` | Svelte-Komponente, bekommt `{ browser }` als Prop |
| `dateiFaehigkeiten?` | Optionale Datei-Fähigkeiten (siehe 5.3) |

### 5.2 Die Ansicht

Die Ansichts-Komponente bekommt **denselben `browser`** wie der Datei-Browser
(dieselbe Instanz). So teilt das Plugin Pfad, Liste und Live-Abgleich:

```svelte
<!-- frontend/src/plugins/meinplugin/Ansicht.svelte -->
<script lang="ts">
  import type { Browser } from "../../lib/browser.svelte";
  interface Props { browser: Browser; }
  let { browser }: Props = $props();
</script>

<div>Im aktuellen Ordner liegen {browser.eintraege.length} Einträge.</div>
```

Nützliche `browser`-Befehle:

- `browser.eintraege` - aktuelle Liste; `browser.pfad` - Brotkrumen; `browser.bereich`.
- `browser.oeffnen(k)` / `browser.oeffneOrdner(k)` - navigieren.
- `browser.oeffnePfad(teile, markiereId?)` - direkt zu einem Ordner über die
  volle Ahnenkette springen und optional eine Datei markieren.
- `browser.zeigeDetail(k)` - Detail-Pane öffnen.

Den App-Wechsel (z.B. zurück auf "dateien") steuerst du über `waehleApp` -
**wichtig: aus `appzustand`, nicht aus der Registry** (siehe Gotcha 6.2):

```ts
import { waehleApp } from "../appzustand.svelte";
waehleApp("dateien");
```

### 5.3 Datei-Fähigkeiten (optional)

Damit verleiht ein Plugin bestimmten Dateien Zusatz-Fähigkeiten, die im
**Normalmodus** greifen (nicht nur in der App-Ansicht). Jede Fähigkeit liefert
pro Dateityp eine Vorschau (im Detail-Pane) und/oder eine Vollansicht (Overlay):

```ts
import type { Knoten } from "../../lib/types";
import Vorschau from "./Vorschau.svelte";
import Vollbild from "./Vollbild.svelte";

const plugin: AppPlugin = {
  // ... wie oben ...
  dateiFaehigkeiten: [
    {
      id: "bild",
      passt: (k: Knoten) => k.typ === "datei" && istBild(k.name),
      vorschau: Vorschau,     // Component<{ knoten, browser }>
      vollansicht: Vollbild,  // Component<{ knoten, browser, schliessen }>
    },
  ],
};
```

Der Kern löst für **nur aktive** Plugins auf und rendert die Komponente,
ohne das Plugin direkt zu kennen. `passt(k)` entscheidet, für welche Knoten die
Fähigkeit gilt.

## 6. Regeln und Gotchas

Diese Punkte sind die häufigsten Stolpersteine - bitte genau beachten.

### 6.1 Aktiv/Inaktiv wirkt erst nach Neustart

Ein neu entdecktes Plugin ist **immer inaktiv**. Aktivieren und Deaktivieren
schreiben nur ein Flag; wirksam wird es erst beim nächsten Backend-Neustart
(Starlette hängt Router zur Laufzeit nicht sauber ab). Die Oberfläche sagt das
ehrlich ("wirkt nach Neustart").

### 6.2 Plugin darf nicht aus der Registry importieren

Die Registry sammelt Plugins per `import.meta.glob` ein. Importiert ein Plugin
seinerseits etwas aus `registry.svelte`, entsteht ein Importzyklus
(`registry -> plugin -> registry`) mit dem Fehler "Cannot access 'X' before
initialization". Darum liegt der App-Auswahl-Zustand in `plugins/appzustand.svelte`
(plugin-frei). **`waehleApp` immer aus `appzustand.svelte` importieren.**

### 6.3 Echte Umlaute, aber ASCII für Bezeichner und API-Werte

In allen sichtbaren Texten echte Umlaute (ä, ö, ü, ß). ASCII gilt nur für
technische Bezeichner (Variablen, CSS-Klassen) und für feste API-Werte, etwa
den Query-Parameter `daten=loeschen|behalten`.

### 6.4 Repo-Plugin vs. Upload-Plugin

Es gibt zwei Herkünfte:

- **`repo`** - der Quellcode liegt versioniert im Git-Baum (so wird normalerweise
  entwickelt und ausgeliefert).
- **`upload`** - per ZIP über die Verwaltung -> Apps installiert.

Beim **Deinstallieren** verhalten sie sich unterschiedlich: Bei `repo` wird nur
der DB-Eintrag entfernt, die Quellordner bleiben - der Lader entdeckt sie beim
nächsten Neustart wieder und registriert das Plugin erneut (inaktiv). Ein
Repo-Plugin lässt sich also über die Oberfläche allein nicht dauerhaft
entfernen; dazu müssen die Ordner aus dem Baum. Nur `upload`-Plugins räumen
beim Deinstallieren auch ihre Ordner weg.

### 6.5 Secure-Context-Browser-APIs

Über die LAN-IP per http (kein HTTPS, kein localhost) sind "secure context"-APIs
nicht verfügbar (z.B. `crypto.randomUUID`, `crypto.subtle`, Clipboard). Nutze im
Frontend Fallbacks - für IDs den Kern-Helfer `eindeutigeId()` aus `lib/id.ts`.

## 7. Entwickeln und testen (Mac-first)

1. Lege die beiden Ordner an (`backend/plugins/<id>/`,
   `frontend/src/plugins/<id>/`) und schreibe Manifest, Backend- und Frontend-Teil.
2. Backend neu starten. Das Plugin wird entdeckt und **inaktiv** in der Tabelle
   `plugin` eingetragen. Im Dev-Modus zieht Vite den Frontend-Teil automatisch.
3. In der Oberfläche: dein Kürzel -> **Verwaltung** -> **Apps**. Dort das
   Plugin per Schalter aktivieren.
4. Backend erneut neu starten, damit die Aktivierung greift (Router + Schema).
5. Prüfen: Erscheint die App in der App-Leiste? Funktioniert die Ansicht?
   Werden eigene Tabellen im Schema `plugin_<id>` angelegt?

Ein defektes Plugin erscheint in der Apps-Liste mit einem Fehlertext (`defekt`),
ohne den Kern zu beeinträchtigen.

## 8. Paketieren als ZIP (für den Upload-Weg)

Für die Installation über die Apps-Seite wird ein ZIP mit folgendem Layout
erwartet (präfix-tolerant, ein umschließender Wurzelordner ist erlaubt):

```
plugin.json            ->  backend/plugins/<id>/plugin.json
backend/...            ->  backend/plugins/<id>/...
frontend/...           ->  frontend/src/plugins/<id>/...
```

Also: `plugin.json` an die Wurzel, der Backend-Inhalt unter `backend/`, der
Frontend-Inhalt unter `frontend/`. Beispiel zum Bauen:

```bash
cd backend/plugins/<id>
zip -r /pfad/<id>.zip plugin.json __init__.py api.py dienst.py schema
cd ../../../frontend/src/plugins/<id>
zip -r /pfad/<id>.zip . -x '*/__pycache__/*'   # landet unter frontend/ im Ziel
```

Der Installer ist abgesichert: Zip-Slip wird verhindert (kein Ausbruch aus den
Zielordnern), es gibt Größen- und Dateizahl-Grenzen, und bei jedem Fehler wird
sauber zurückgesetzt (keine halbe Installation). Existiert das Plugin bereits,
wird der Upload mit 409 abgelehnt.

## 9. Installieren, aktivieren, deinstallieren (Verwaltung -> Apps)

- **Hochladen**: "App hochladen (ZIP)" -> Datei wählen. Das Plugin erscheint
  inaktiv mit Quelle `upload`.
- **Aktivieren/Deaktivieren**: Schalter. Wirkt nach Neustart.
- **Deinstallieren**: mit Rückfrage, ob die eigenen Daten (Schema `plugin_<id>`)
  mitgelöscht werden. Bei `upload`-Plugins werden auch die Ordner entfernt.

## 10. Referenz: das Medien-Plugin

Das mitgelieferte Plugin `medien` ist die vollständige Referenzumsetzung. Es
zeigt Bilder und Audio in einer Ansicht und geht damit über eine reine
Bildergalerie hinaus:

- Backend: serverseitige WebP-Thumbnails (Pillow, plattengecacht), HEIC optional
  (pillow-heif), Audio-Streaming, Endpunkte
  `/api/v1/plugins/medien/thumb|inline|stream|alle` mit Token-Auth, Zugriff nur
  über `kontext.speicher`.
- Frontend: App-Ansicht mit Kachel/Liste, zentraler Ansicht über alle Ordner,
  Bild-Lightbox mit Diashow und Audio-Wiedergabe über die globale Player-Leiste
  des Kerns. Zusätzlich Datei-Fähigkeiten (Bild-Vorschau + Vollbild, Audio-
  Vorschau im Detail-Pane). Das Raster baut bewusst auf den Kern-Klassen
  (`.grid`/`.kachel`/`.vorschau`) auf, statt ein eigenes nachzubauen.

Es eignet sich als Vorlage für eigene Plugins: Kernkomponenten nutzen, nur
medienspezifische Zusätze selbst mitbringen.

## 11. Offener Architektur-Punkt

Aktuell ist der Frontend-Teil über `import.meta.glob` **zur Bauzeit** in den
Core eingebunden; ein per ZIP hochgeladenes Plugin braucht daher den vite-Dev-
Server (Live-Pickup) oder einen Frontend-Neubau. Eine Weiterentwicklung in
Richtung "Plugins komplett entkoppelt, vorab kompiliert, zur Laufzeit
nachgeladen" ist angedacht; dieser Abschnitt wird dann aktualisiert.

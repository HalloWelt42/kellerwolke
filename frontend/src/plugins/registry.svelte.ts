import type { Component } from "svelte";
import * as api from "../lib/api";
import type { Browser } from "../lib/browser.svelte";
import type { Knoten } from "../lib/types";
import Dateiliste from "../lib/Dateiliste.svelte";
import type { AppPlugin, DateiFaehigkeit } from "./typen";
import { DEFAULT_APP_ID, appZustand, waehleApp } from "./appzustand.svelte";

// Zentrale App-Registry. Der Datei-Browser ist die fest eingebaute Default-App
// (KEIN Plugin). Plugin-Apps werden ISOLIERT und LAZY geladen: nur die aktiven
// Plugins werden per dynamischem Import geholt, jedes in eigenem try/catch. Ein
// kaputtes Plugin (z.B. fehlender Import) faellt damit fuer sich aus und wird
// automatisch deaktiviert - es kann die Hauptanwendung NICHT mehr mitreissen.
// (Frueher: eager import.meta.glob -> ein Fehler kippte das ganze Bundle.)
// Der App-Auswahl-Zustand liegt bewusst plugin-frei in [[appzustand]].
export { DEFAULT_APP_ID, appZustand, waehleApp };

const standardApp: AppPlugin = {
  id: DEFAULT_APP_ID,
  label: "Dateien",
  icon: "fa-solid fa-folder",
  reihenfolge: 0,
  ansicht: Dateiliste as unknown as Component<{ browser: Browser }>,
};

// Lazy: liefert je Plugin eine Ladefunktion (kein eager) - so landet KEIN
// Plugin-Code im Haupt-Bundle, jedes wird ein eigener, nachladbarer Brocken.
const module = import.meta.glob("./*/plugin.ts");
const loaderFuer: Record<string, () => Promise<unknown>> = {};
for (const [pfad, loader] of Object.entries(module)) {
  const treffer = pfad.match(/^\.\/([^/]+)\/plugin\.ts$/);
  if (treffer) loaderFuer[treffer[1]] = loader as () => Promise<unknown>;
}

// Erfolgreich geladene, aktive Plugin-Apps (reaktiv - fuellt sich nach dem
// asynchronen Laden; die Oberflaeche zeigt sie dann an).
let geladenePlugins = $state<AppPlugin[]>([]);

export async function ladeAktiveApps(): Promise<void> {
  let aktive: { id: string }[] = [];
  try {
    aktive = await api.aktiveApps();
  } catch {
    appZustand.aktivierteIds = [];
    geladenePlugins = [];
    return;
  }
  appZustand.aktivierteIds = aktive.map((a) => a.id);
  const geladen: AppPlugin[] = [];
  for (const a of aktive) {
    const loader = loaderFuer[a.id];
    if (!loader) continue; // reines Backend-Plugin oder Frontend-Teil (noch) nicht da
    try {
      const mod = (await loader()) as { default?: AppPlugin };
      if (mod.default) geladen.push(mod.default);
    } catch (e) {
      // Kaputtes Plugin darf die App NICHT mitreissen: rausnehmen und
      // serverseitig automatisch deaktivieren, damit es nicht bei jedem Laden
      // erneut scheitert. Admin kann es nach der Reparatur wieder einschalten.
      console.error(`Plugin "${a.id}" laedt nicht - wird automatisch deaktiviert:`, e);
      appZustand.aktivierteIds = appZustand.aktivierteIds.filter((id) => id !== a.id);
      try {
        await api.pluginMeldeDefekt(a.id, e instanceof Error ? e.message : String(e));
      } catch {
        // Melden fehlgeschlagen - lokal ist es trotzdem raus.
      }
    }
  }
  geladenePlugins = geladen;
}

// Ein Plugin zur Laufzeit (z.B. nach einem Render-Fehler in der Fehlergrenze)
// als defekt melden und lokal entfernen.
export async function meldePluginDefekt(id: string, grund: string): Promise<void> {
  appZustand.aktivierteIds = appZustand.aktivierteIds.filter((x) => x !== id);
  geladenePlugins = geladenePlugins.filter((p) => p.id !== id);
  if (appZustand.aktivId === id) waehleApp(DEFAULT_APP_ID);
  try {
    await api.pluginMeldeDefekt(id, grund);
  } catch {
    // egal - lokal ist es raus
  }
}

// Default + geladene aktive Plugin-Apps, nach reihenfolge sortiert.
export function sichtbareApps(): AppPlugin[] {
  return [standardApp, ...geladenePlugins].sort(
    (a, b) => (a.reihenfolge ?? 99) - (b.reihenfolge ?? 99),
  );
}

export function aktiveApp(): AppPlugin {
  return sichtbareApps().find((a) => a.id === appZustand.aktivId) ?? standardApp;
}

// --- Datei-Faehigkeiten (nur geladener, aktiver Plugins) --------------------

function aktiveFaehigkeiten(): DateiFaehigkeit[] {
  return geladenePlugins.flatMap((p) => p.dateiFaehigkeiten ?? []);
}

// Erste passende Vorschau-Faehigkeit fuer den Knoten (oder null).
export function vorschauFuer(k: Knoten): DateiFaehigkeit | null {
  return aktiveFaehigkeiten().find((f) => f.vorschau && f.passt(k)) ?? null;
}

// Erste passende Vollansicht-Faehigkeit fuer den Knoten (oder null).
export function vollansichtFuer(k: Knoten): DateiFaehigkeit | null {
  return aktiveFaehigkeiten().find((f) => f.vollansicht && f.passt(k)) ?? null;
}

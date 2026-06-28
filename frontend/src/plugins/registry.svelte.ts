import type { Component } from "svelte";
import * as api from "../lib/api";
import type { Browser } from "../lib/browser.svelte";
import Dateiliste from "../lib/Dateiliste.svelte";
import type { AppPlugin } from "./typen";

// Zentrale App-Registry. Der Datei-Browser ist die fest eingebaute Default-App
// (KEIN Plugin). Alle Plugin-Apps werden zur Build-Zeit per import.meta.glob
// eingesammelt und zur Laufzeit gegen die vom Backend gemeldeten AKTIVEN
// Plugins gefiltert.

export const DEFAULT_APP_ID = "dateien";

const standardApp: AppPlugin = {
  id: DEFAULT_APP_ID,
  label: "Dateien",
  icon: "fa-solid fa-folder",
  reihenfolge: 0,
  // wird von App.svelte nie ueber .ansicht gerendert (Default hat ihren eigenen
  // Block), nur fuer den App-Leisten-Eintrag noetig.
  ansicht: Dateiliste as unknown as Component<{ browser: Browser }>,
};

const module = import.meta.glob("./*/plugin.ts", { eager: true });
const pluginApps: AppPlugin[] = Object.values(module)
  .map((m) => (m as { default?: AppPlugin }).default)
  .filter((p): p is AppPlugin => !!p);

export const appZustand = $state<{ aktivId: string; aktivierteIds: string[] }>({
  aktivId: DEFAULT_APP_ID,
  aktivierteIds: [],
});

export async function ladeAktiveApps(): Promise<void> {
  try {
    const aktive = await api.aktiveApps();
    appZustand.aktivierteIds = aktive.map((a) => a.id);
  } catch {
    appZustand.aktivierteIds = [];
  }
}

// Default + aktive Plugin-Apps, nach reihenfolge sortiert.
export function sichtbareApps(): AppPlugin[] {
  const aktive = pluginApps.filter((p) => appZustand.aktivierteIds.includes(p.id));
  return [standardApp, ...aktive].sort(
    (a, b) => (a.reihenfolge ?? 99) - (b.reihenfolge ?? 99),
  );
}

export function aktiveApp(): AppPlugin {
  return sichtbareApps().find((a) => a.id === appZustand.aktivId) ?? standardApp;
}

export function waehleApp(id: string): void {
  appZustand.aktivId = id;
}

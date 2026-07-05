// Reiner App-Auswahl-Zustand OHNE Plugin-Importe. Bewusst getrennt von der
// Registry (die per import.meta.glob alle Plugins laedt): so darf ein Plugin den
// App-Wechsel nutzen, ohne einen Importzyklus registry -> plugin -> registry zu
// erzeugen. Hier liegen auch die geladenen Plugins + die Aufloesung der
// Datei-Faehigkeiten - damit KERN-Komponenten (die die Registry NICHT importieren
// duerfen, weil die Registry sie laedt, z.B. Dateiliste) sie trotzdem nutzen.
import type { AppPlugin, DateiFaehigkeit } from "./typen";
import type { Knoten } from "../lib/types";

export const DEFAULT_APP_ID = "dateien";

export const appZustand = $state<{ aktivId: string; aktivierteIds: string[] }>({
  aktivId: DEFAULT_APP_ID,
  aktivierteIds: [],
});

// Eine App in der App-Leiste auswaehlen (z.B. zurueck auf "dateien").
export function waehleApp(id: string): void {
  appZustand.aktivId = id;
}

// Erfolgreich geladene, aktive Plugin-Apps (von der Registry befuellt, reaktiv).
export const pluginZustand = $state<{ geladen: AppPlugin[] }>({ geladen: [] });

function aktiveFaehigkeiten(): DateiFaehigkeit[] {
  return pluginZustand.geladen.flatMap((p) => p.dateiFaehigkeiten ?? []);
}
// Erste passende Vorschau- bzw. Vollansicht-Faehigkeit fuer den Knoten (oder null).
export function vorschauFuer(k: Knoten): DateiFaehigkeit | null {
  return aktiveFaehigkeiten().find((f) => f.vorschau && f.passt(k)) ?? null;
}
export function vollansichtFuer(k: Knoten): DateiFaehigkeit | null {
  return aktiveFaehigkeiten().find((f) => f.vollansicht && f.passt(k)) ?? null;
}

import type { Component } from "svelte";
import type { Bereich, Browser } from "../lib/browser.svelte";

// Vertrag fuer jede Ansichts-App (Plugin). Ein Plugin exportiert genau ein
// solches Objekt als default aus seiner plugin.ts. Die Ansicht bekommt IMMER
// den aktiven Browser (dieselbe Instanz wie der Datei-Browser) - so teilen App
// und Datei-Browser Pfad, Liste, Live-Abgleich ohne Sonderfall.
export interface AppPlugin {
  id: string;
  label: string;
  icon: string; // Font-Awesome-Klasse
  reihenfolge?: number;
  bereiche?: Bereich[]; // wo die App sinnvoll ist; fehlt = ueberall
  ansicht: Component<{ browser: Browser }>;
}

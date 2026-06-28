import type { Component } from "svelte";
import type { Bereich, Browser } from "../lib/browser.svelte";
import type { Knoten } from "../lib/types";

// Datei-Faehigkeit: ein Plugin verleiht bestimmten Dateien Zusatz-Faehigkeiten,
// die im NORMALMODUS (nicht nur in der App-Ansicht) greifen. Trifft `passt` zu,
// kann der Kern die Vorschau (im Detail-Pane) bzw. die Vollansicht (Lightbox)
// des Plugins rendern - ohne das Plugin direkt zu kennen (Aufloesung ueber die
// Registry). Beispiel Galerie: Bild-Thumbnail + Vollbild. Spaeter denkbar:
// Video-Player, PDF-Seiten, Audio-Wellenform.
export interface DateiFaehigkeit {
  id: string;
  passt: (k: Knoten) => boolean;
  // Eingebettete Vorschau im Detail-Pane (klein, statt des generischen Symbols).
  vorschau?: Component<{ knoten: Knoten; browser: Browser }>;
  // Vollansicht als Overlay; `schliessen` blendet sie wieder aus.
  vollansicht?: Component<{ knoten: Knoten; browser: Browser; schliessen: () => void }>;
}

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
  // Optionale Datei-Faehigkeiten, die im Normalmodus wirken (nur wenn Plugin aktiv).
  dateiFaehigkeiten?: DateiFaehigkeit[];
}

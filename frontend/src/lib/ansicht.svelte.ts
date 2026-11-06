// Wie eine Fläche ihre Einträge zeigt (KW-5): Es gibt keine eigene Medienansicht mehr, nur die Ansicht Dateien. Der
// Filter nach Art wählt Inhalt UND Darstellung: Bilder randlos mit Vollbild und Diashow, Audio als Titelliste mit
// Dauer, Video mit Standbild und Dauer. Kacheln gibt es in drei Größen. Der Zustand selbst liegt je Fläche in der
// Browser-Klasse (art, kachelgroesse); hier stehen nur die Arten, Größen und ihre Beschriftung (Symbol, Hover).
import type { Bereich } from "./browser.svelte";
import type { Medienart } from "./types";

export type Artfilter = "alle" | Medienart;
export type Kachelgroesse = "klein" | "mittel" | "gross";

export interface Artwahl {
  id: Artfilter;
  icon: string;
  titel: string; // steht im Hover, die Knöpfe zeigen nur Symbol und Anzahl
}

export const ARTEN: Artwahl[] = [
  { id: "alle", icon: "fa-solid fa-border-all", titel: "Alles in diesem Ordner" },
  { id: "bild", icon: "fa-regular fa-image", titel: "Bilder: randlose Fotos, Vollbild und Diashow" },
  { id: "audio", icon: "fa-solid fa-music", titel: "Audio: Titelliste mit Dauer, alles abspielen" },
  { id: "video", icon: "fa-solid fa-film", titel: "Video: Standbilder mit Dauer, Abspielen" },
];

export const KACHELGROESSEN: { id: Kachelgroesse; icon: string; titel: string }[] = [
  { id: "klein", icon: "fa-solid fa-table-cells", titel: "Kacheln klein" },
  { id: "mittel", icon: "fa-solid fa-table-cells-large", titel: "Kacheln mittel" },
  { id: "gross", icon: "fa-regular fa-square", titel: "Kacheln groß (doppelt)" },
];

// Wo der Filter nach Art gilt: wo Dateien des Kontos liegen. Im Papierkorb und in externen Quellen zeigt die Fläche alles.
export const ARTEN_BEREICHE: Bereich[] = ["dateien", "favoriten", "geteilt", "suche"];

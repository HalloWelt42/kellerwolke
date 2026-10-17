// Zentrale Vollansicht im Kern: Bilder und Videos einer Liste, mit Blättern
// und Diashow. Einmal in App.svelte gerendert; geöffnet von überall
// (Dateiliste, Detail, Medienansicht), immer mit den Nachbarn der Ansicht.
import type { MedienEintrag } from "./medien/adressen";

export const vollansicht = $state<{
  liste: MedienEintrag[];
  index: number; // -1 = zu
  diashow: boolean;
  intervall: number; // Sekunden je Bild
}>({ liste: [], index: -1, diashow: false, intervall: 4 });

export function vollansichtOffen(): boolean {
  return vollansicht.index >= 0;
}

export function aktuellesVoll(): MedienEintrag | null {
  return vollansicht.index >= 0 ? (vollansicht.liste[vollansicht.index] ?? null) : null;
}

export function oeffneVollansicht(liste: MedienEintrag[], index: number, diashow = false): void {
  const sichtbar = liste.filter((m) => m.art === "bild" || m.art === "video");
  const ziel = liste[index];
  const i = ziel ? sichtbar.findIndex((m) => m.id === ziel.id) : 0;
  if (!sichtbar.length || i < 0) return;
  vollansicht.liste = sichtbar;
  vollansicht.index = i;
  vollansicht.diashow = diashow;
}

export function schliesseVollansicht(): void {
  vollansicht.index = -1;
  vollansicht.diashow = false;
  vollansicht.liste = [];
}

// Blättern mit Umlauf; die Diashow überspringt Videos.
export function vollBlaettern(schritt: 1 | -1, nurBilder = false): void {
  const n = vollansicht.liste.length;
  if (!n || vollansicht.index < 0) return;
  let i = vollansicht.index;
  for (let versuch = 0; versuch < n; versuch++) {
    i = (i + schritt + n) % n;
    if (!nurBilder || vollansicht.liste[i].art === "bild") break;
  }
  vollansicht.index = i;
}

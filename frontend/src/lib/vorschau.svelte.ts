// Zentrale Vollansicht (Lightbox) im Kern - von UEBERALL oeffenbar (Doppelklick in
// der Dateiliste, Knopf im Detail-Pane, kuenftig Plugins) und einmalig in
// App.svelte ueber die Datei-Faehigkeit des aktiven Plugins gerendert. So bekommt
// jede Ansicht dieselbe Vorschau, ohne dass jemand etwas nachbaut.
import type { Knoten } from "./types";

export const vorschauZustand = $state<{ knoten: Knoten | null }>({ knoten: null });

export function oeffneVollansicht(k: Knoten): void {
  vorschauZustand.knoten = k;
}
export function schliesseVollansicht(): void {
  vorschauZustand.knoten = null;
}

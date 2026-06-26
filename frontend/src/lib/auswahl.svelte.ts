import { SvelteSet } from "svelte/reactivity";

// Auswahl-Zustand fuer Liste und Kacheln. Haelt die Menge gewaehlter Knoten-IDs
// und einen Anker fuer die Shift-Bereichsauswahl. Reine Auswahl-Logik, frei von
// Darstellung: Einfachklick waehlt einzeln, Strg-Klick schaltet um, Shift-Klick
// waehlt den Bereich ab dem Anker, das Maus-Rechteck (Marquee) ersetzt oder
// vereinigt Mengen.

const ids = new SvelteSet<string>();
let anker = $state<string | null>(null);

export const auswahl = {
  get ids(): SvelteSet<string> {
    return ids;
  },
  get anzahl(): number {
    return ids.size;
  },
  istGewaehlt(id: string): boolean {
    return ids.has(id);
  },
  leeren(): void {
    ids.clear();
    anker = null;
  },
  waehleEinzeln(id: string): void {
    ids.clear();
    ids.add(id);
    anker = id;
  },
  umschalten(id: string): void {
    if (ids.has(id)) ids.delete(id);
    else ids.add(id);
    anker = id;
  },
  bereich(ziel: string, geordnet: string[]): void {
    const start = anker ?? ziel;
    const i = geordnet.indexOf(start);
    const j = geordnet.indexOf(ziel);
    if (i === -1 || j === -1) {
      this.waehleEinzeln(ziel);
      return;
    }
    const [von, bis] = i <= j ? [i, j] : [j, i];
    ids.clear();
    for (let k = von; k <= bis; k++) ids.add(geordnet[k]);
    // Anker bleibt der urspruengliche Startpunkt fuer weitere Shift-Klicks.
  },
  alle(geordnet: string[]): void {
    ids.clear();
    for (const id of geordnet) ids.add(id);
    anker = geordnet[geordnet.length - 1] ?? null;
  },
  ersetze(neue: Iterable<string>): void {
    ids.clear();
    for (const id of neue) ids.add(id);
  },
  vereinige(weitere: Iterable<string>): void {
    for (const id of weitere) ids.add(id);
  },
  // Behaelt nur IDs, die noch sichtbar sind (nach Nachladen/Loeschen).
  beschraenkeAuf(vorhandene: Iterable<string>): void {
    const erlaubt = new Set(vorhandene);
    for (const id of ids) {
      if (!erlaubt.has(id)) ids.delete(id);
    }
    if (anker && !erlaubt.has(anker)) anker = null;
  },
};

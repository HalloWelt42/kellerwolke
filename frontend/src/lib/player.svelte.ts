// Globaler Audio-Player-Zustand. Liegt bewusst im Kern, damit die Player-Leiste
// die App-Navigation ueberlebt (spielt weiter, waehrend man browst oder die App
// wechselt). Plugins (z.B. Medien) fuellen die Liste und starten die Wiedergabe;
// gerendert wird die Leiste einmalig in App.svelte.

export interface Spur {
  id: string;
  url: string; // Stream-URL
  titel: string;
  pfad: { id: string; name: string }[] | null; // Ordnerkette (fuer "Zum Ordner")
}

export const player = $state<{
  liste: Spur[];
  index: number; // -1 = nichts aktiv
  laeuft: boolean;
  zeit: number;
  dauer: number;
}>({ liste: [], index: -1, laeuft: false, zeit: 0, dauer: 0 });

export function aktuelleSpur(): Spur | null {
  return player.index >= 0 && player.index < player.liste.length ? player.liste[player.index] : null;
}
export function spielen(liste: Spur[], index: number): void {
  player.liste = liste;
  player.index = index;
}
export function spurWeiter(): void {
  if (player.liste.length) player.index = (player.index + 1) % player.liste.length;
}
export function spurZurueck(): void {
  if (player.liste.length) player.index = (player.index - 1 + player.liste.length) % player.liste.length;
}
export function playerBeenden(): void {
  player.liste = [];
  player.index = -1;
  player.laeuft = false;
  player.zeit = 0;
  player.dauer = 0;
}

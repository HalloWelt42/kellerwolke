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

export type Wiederholung = "aus" | "eine" | "alle";

export const player = $state<{
  liste: Spur[];
  index: number; // -1 = nichts aktiv
  laeuft: boolean;
  zeit: number;
  dauer: number;
  lautstaerke: number; // 0..1
  stumm: boolean;
  wiederholung: Wiederholung;
  zufall: boolean;
}>({
  liste: [],
  index: -1,
  laeuft: false,
  zeit: 0,
  dauer: 0,
  lautstaerke: 1,
  stumm: false,
  wiederholung: "aus",
  zufall: false,
});

export function aktuelleSpur(): Spur | null {
  return player.index >= 0 && player.index < player.liste.length ? player.liste[player.index] : null;
}
export function spielen(liste: Spur[], index: number): void {
  player.liste = liste;
  player.index = index;
}

function zufallsIndex(): number {
  const n = player.liste.length;
  if (n <= 1) return player.index;
  let k: number;
  do {
    k = Math.floor(Math.random() * n);
  } while (k === player.index);
  return k;
}

// Manuelle Tasten (Weiter/Zurueck): immer wechseln, mit Umlauf.
export function spurWeiter(): void {
  const n = player.liste.length;
  if (!n) return;
  player.index = player.zufall ? zufallsIndex() : (player.index + 1) % n;
}
export function spurZurueck(): void {
  const n = player.liste.length;
  if (!n) return;
  player.index = player.zufall ? zufallsIndex() : (player.index - 1 + n) % n;
}

// Track zu Ende: Wiederholung/Zufall beruecksichtigen. Rueckgabe sagt der Leiste,
// was zu tun ist (bei "wiederhole" bleibt der Index gleich -> selbst zuruecksetzen).
export function beiEnde(): "wiederhole" | "weiter" | "stopp" {
  const n = player.liste.length;
  if (!n) return "stopp";
  if (player.wiederholung === "eine") return "wiederhole";
  if (player.zufall) {
    player.index = zufallsIndex();
    return "weiter";
  }
  if (player.index + 1 < n) {
    player.index += 1;
    return "weiter";
  }
  if (player.wiederholung === "alle") {
    player.index = 0;
    return "weiter";
  }
  return "stopp";
}

// Wiederholung durchschalten: aus -> alle -> eine -> aus.
export function wiederholungWeiter(): void {
  player.wiederholung = player.wiederholung === "aus" ? "alle" : player.wiederholung === "alle" ? "eine" : "aus";
}

export function playerBeenden(): void {
  player.liste = [];
  player.index = -1;
  player.laeuft = false;
  player.zeit = 0;
  player.dauer = 0;
}

// --- Reload-Persistenz. Fuers versehentliche Neuladen: aktuelle Liste, Position
// und Modi im lokalen Speicher. Die Stream-URLs gelten innerhalb der Sitzung -
// nach einem echten Neustart der Sitzung koennen sie ablaufen (dann greift der
// Fehlerzustand der Leiste). ---
const SCHLUESSEL = "kw_player";

export function zustandLaden(): number {
  // Setzt Liste/Index/Modi aus dem Speicher; gibt die gemerkte Sekunde zurueck.
  try {
    const roh = localStorage.getItem(SCHLUESSEL);
    if (!roh) return 0;
    const d = JSON.parse(roh);
    if (Array.isArray(d.liste) && d.liste.length && typeof d.index === "number") {
      player.liste = d.liste;
      player.index = Math.min(Math.max(0, d.index), d.liste.length - 1);
    }
    if (typeof d.lautstaerke === "number") player.lautstaerke = Math.min(1, Math.max(0, d.lautstaerke));
    if (typeof d.stumm === "boolean") player.stumm = d.stumm;
    if (d.wiederholung === "aus" || d.wiederholung === "eine" || d.wiederholung === "alle") player.wiederholung = d.wiederholung;
    if (typeof d.zufall === "boolean") player.zufall = d.zufall;
    return typeof d.zeit === "number" ? d.zeit : 0;
  } catch {
    return 0;
  }
}

export function zustandSpeichern(): void {
  try {
    localStorage.setItem(
      SCHLUESSEL,
      JSON.stringify({
        liste: player.liste,
        index: player.index,
        zeit: player.zeit,
        lautstaerke: player.lautstaerke,
        stumm: player.stumm,
        wiederholung: player.wiederholung,
        zufall: player.zufall,
      }),
    );
  } catch {
    // Speicher voll/blockiert - Persistenz ist Komfort, kein Muss.
  }
}

// Globaler Audio-Player-Zustand. Liegt bewusst im Kern, damit die Player-Leiste
// die App-Navigation überlebt (spielt weiter, während man browst oder die
// Ansicht wechselt). Dateiliste, Detail und Medienansicht füllen die Liste und
// starten die Wiedergabe; gerendert wird die Leiste einmalig in App.svelte.
import { stromUrl } from "./medien/adressen";
import type { Pfadteil } from "./types";

export interface Spur {
  id: string;
  etag: string | null; // Versionsstand: Teil der Adresse
  titel: string;
  pfad: Pfadteil[] | null; // Ordnerkette (für "Zum Ordner"); null = unbekannt
}

export function spurUrl(s: Spur): string {
  return stromUrl(s);
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
  tempo: number; // Wiedergabegeschwindigkeit, 1 = normal
  voll: boolean; // Now-Playing-Ansicht offen
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
  tempo: 1,
  voll: false,
});

export function aktuelleSpur(): Spur | null {
  return player.index >= 0 && player.index < player.liste.length ? player.liste[player.index] : null;
}
// Startet einen Titel. Ist es der laufende, schaltet der Klick Pause und
// Wiedergabe um; ist er zu Ende, beginnt er von vorn.
export function spielen(liste: Spur[], index: number): void {
  const neu = liste[index];
  const jetzt = aktuelleSpur();
  player.liste = liste;
  player.index = index;
  if (!neu || !jetzt || jetzt.id !== neu.id || jetzt.etag !== neu.etag || !el) return;
  if (el.ended) {
    el.currentTime = 0;
    el.play().catch(() => {});
  } else {
    umschalten();
  }
}

// Das (einzige) Audio-Element meldet sich hier an, damit sowohl die Leiste als
// auch die Now-Playing-Ansicht dieselbe Wiedergabe steuern können.
let el: HTMLAudioElement | null = null;
export function audioElement(a: HTMLAudioElement | null): void {
  el = a;
}
export function umschalten(): void {
  if (!el) return;
  if (el.paused) el.play().catch(() => {});
  else el.pause();
}
export function suchenZu(sekunde: number): void {
  if (el && isFinite(sekunde)) el.currentTime = Math.max(0, sekunde);
}
export function springen(delta: number): void {
  if (!el) return;
  const d = el.duration || 0;
  el.currentTime = Math.max(0, Math.min(d, el.currentTime + delta));
}
export function setzeTempo(t: number): void {
  player.tempo = t;
}
export function springeZuIndex(i: number): void {
  if (i >= 0 && i < player.liste.length) player.index = i;
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

// Manuelle Tasten (Weiter/Zurück): immer wechseln, mit Umlauf.
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

// Track zu Ende: Wiederholung/Zufall berücksichtigen. Rückgabe sagt der Leiste,
// was zu tun ist (bei "wiederhole" bleibt der Index gleich -> selbst zurücksetzen).
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

// --- Reload-Persistenz je Konto: aktuelle Liste, Position und Modi im lokalen
// Speicher, damit ein versehentliches Neuladen nichts verliert. Die Adressen
// hängen am Lesezugang (Cookie), nicht an einem Schlüssel - sie bleiben gültig.
// Ein anderes Konto sieht die Liste nie; Abmelden löscht sie.
const PRAEFIX = "kw_player:";
let schluessel: string | null = null;

export function zustandLaden(konto: string): number {
  // Setzt Liste/Index/Modi aus dem Speicher; gibt die gemerkte Sekunde zurück.
  schluessel = PRAEFIX + konto;
  try {
    localStorage.removeItem("kw_player"); // früherer Schlüssel ohne Konto (mit Sitzungsschlüssel in den Adressen)
    const roh = localStorage.getItem(schluessel);
    if (!roh) return 0;
    const d = JSON.parse(roh);
    const gueltig = (x: unknown): x is Spur =>
      !!x && typeof (x as Spur).id === "string" && typeof (x as Spur).titel === "string";
    if (Array.isArray(d.liste) && d.liste.length && d.liste.every(gueltig) && typeof d.index === "number") {
      player.liste = d.liste;
      player.index = Math.min(Math.max(0, d.index), d.liste.length - 1);
    }
    if (typeof d.lautstaerke === "number") player.lautstaerke = Math.min(1, Math.max(0, d.lautstaerke));
    if (typeof d.stumm === "boolean") player.stumm = d.stumm;
    if (d.wiederholung === "aus" || d.wiederholung === "eine" || d.wiederholung === "alle") player.wiederholung = d.wiederholung;
    if (typeof d.zufall === "boolean") player.zufall = d.zufall;
    if (typeof d.tempo === "number") player.tempo = d.tempo;
    return typeof d.zeit === "number" ? d.zeit : 0;
  } catch {
    return 0;
  }
}

export function zustandSpeichern(): void {
  if (!schluessel) return;
  try {
    localStorage.setItem(
      schluessel,
      JSON.stringify({
        liste: player.liste,
        index: player.index,
        zeit: player.zeit,
        lautstaerke: player.lautstaerke,
        stumm: player.stumm,
        wiederholung: player.wiederholung,
        zufall: player.zufall,
        tempo: player.tempo,
      }),
    );
  } catch {
    // Speicher voll/blockiert - Persistenz ist Komfort, kein Muss.
  }
}

// Abmelden: Wiedergabe beenden und den Merker des Kontos entfernen.
export function playerZuruecksetzen(): void {
  if (el) {
    el.pause();
    el.removeAttribute("src");
  }
  playerBeenden();
  player.voll = false;
  if (schluessel) {
    try {
      localStorage.removeItem(schluessel);
    } catch {
      // egal
    }
  }
  schluessel = null;
}

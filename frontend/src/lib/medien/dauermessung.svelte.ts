// Dauer von Ton und Video, im Browser gemessen (der Server kennt sie nicht): ein Medienelement lädt nur die Kopfdaten
// (preload=metadata, über den Lesezugang mit Bereichen), liest die Länge und gibt die Verbindung wieder frei. Einmal je
// Version gemessen und gemerkt; höchstens wenige gleichzeitig, damit eine lange Liste den Pi nicht flutet.
import { SvelteMap } from "svelte/reactivity";
import { stromUrl } from "./adressen";

const GLEICHZEITIG = 4;
const GEDULD_MS = 20_000;

type Art = "audio" | "video";
interface Messung {
  schluessel: string;
  url: string;
  art: Art;
}

const dauern = new SvelteMap<string, number>(); // Sekunden; NaN = nicht messbar
const angefragt = new Set<string>();
const warteschlange: Messung[] = [];
let laufend = 0;

function schluessel(m: { id: string; etag: string | null }): string {
  return `${m.id}:${m.etag ?? ""}`;
}

/** Die gemessene Dauer in Sekunden; undefined, solange sie noch nicht da ist, NaN, wenn sie sich nicht messen lässt. */
export function dauerVon(m: { id: string; etag: string | null }): number | undefined {
  return dauern.get(schluessel(m));
}

/** Messung anstoßen (einmal je Version); das Ergebnis kommt über dauerVon. */
export function dauerAnfordern(m: { id: string; etag: string | null }, art: Art): void {
  const s = schluessel(m);
  if (angefragt.has(s)) return;
  angefragt.add(s);
  warteschlange.push({ schluessel: s, url: stromUrl(m), art });
  weiter();
}

function weiter(): void {
  while (laufend < GLEICHZEITIG && warteschlange.length) {
    const m = warteschlange.shift()!;
    laufend += 1;
    messen(m).finally(() => {
      laufend -= 1;
      weiter();
    });
  }
}

function messen(m: Messung): Promise<void> {
  return new Promise((fertig) => {
    const el = document.createElement(m.art);
    el.preload = "metadata";
    el.muted = true;
    const ende = (sekunden: number) => {
      clearTimeout(uhr);
      el.removeAttribute("src");
      el.load(); // gibt die Verbindung frei
      dauern.set(m.schluessel, sekunden);
      fertig();
    };
    const uhr = setTimeout(() => ende(NaN), GEDULD_MS);
    el.onloadedmetadata = () => ende(isFinite(el.duration) ? el.duration : NaN);
    el.onerror = () => ende(NaN);
    el.src = m.url;
  });
}

/** mm:ss bzw. h:mm:ss; "-" ohne Wert. */
export function dauerText(s: number | undefined): string {
  if (s === undefined || !isFinite(s)) return "-";
  const g = Math.round(s);
  const h = Math.floor(g / 3600);
  const min = Math.floor((g % 3600) / 60);
  const sek = (g % 60).toString().padStart(2, "0");
  return h ? `${h}:${min.toString().padStart(2, "0")}:${sek}` : `${min}:${sek}`;
}

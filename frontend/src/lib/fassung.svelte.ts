// Neue Fassung auf dem Server: nie ein hartes Neuladen verlangen (Muster aus Orbit).
// Die Startseite kommt ohne Zwischenspeicher, die Skripte und Gestaltung tragen Prüfsummen im Namen. Meldet der Server
// eine andere Fassung als die eingebaute, lädt die Seite von selbst neu: in den ersten Sekunden nach dem Start sofort,
// später beim nächsten Ortswechsel oder wenn das Fenster wieder nach vorn kommt. Nie, solange hochgeladen oder
// abgespielt wird; dann wartet sie bis danach. Dazwischen steht ein Band mit Knopf. Je Serverfassung nur ein
// selbsttätiger Versuch (Merker in der Sitzung), damit ein hängender Zwischenspeicher keine Schleife auslöst.
import * as api from "./api";
import { player } from "./player.svelte";
import { zustand } from "./zustand.svelte";

export const OBERFLAECHE_FASSUNG = __FASSUNG__;
const MERKER = "kellerwolke.neu_geladen";
const START_FENSTER_MS = 10_000;
const PRUEFEN_MS = 60_000;

export const fassung = $state<{ neu: string | null }>({ neu: null });

export type Anlass = "start" | "takt" | "ortswechsel" | "sichtbar";

// Nichts, was ein Neuladen abbrechen würde.
export function ruhig(): boolean {
  return !player.laeuft && !zustand.uploads.some((u) => u.status === "wartet" || u.status === "laeuft");
}

function erlaubt(neu: string): boolean {
  try {
    if (sessionStorage.getItem(MERKER) === neu) return false;
    sessionStorage.setItem(MERKER, neu);
  } catch {
    // ohne Sitzungsspeicher kein Merker: dann lieber einmal laden als nie
  }
  return true;
}

export function vielleichtNeuLaden(anlass: Anlass): void {
  const neu = fassung.neu;
  if (!neu || anlass === "takt" || !ruhig()) return;
  if (anlass === "start" && performance.now() > START_FENSTER_MS) return;
  if (erlaubt(neu)) location.reload();
}

export async function fassungPruefen(anlass: Anlass): Promise<void> {
  try {
    const server = await api.version();
    zustand.version = server;
    fassung.neu = server !== OBERFLAECHE_FASSUNG ? server : null;
  } catch {
    return; // ohne Verbindung meldet das Band der Verbindung
  }
  vielleichtNeuLaden(anlass);
}

function sichtbar(): void {
  if (document.visibilityState === "visible") fassungPruefen("sichtbar");
}

export function fassungVerfolgen(): () => void {
  fassungPruefen("start");
  const takt = setInterval(() => fassungPruefen("takt"), PRUEFEN_MS);
  document.addEventListener("visibilitychange", sichtbar);
  return () => {
    clearInterval(takt);
    document.removeEventListener("visibilitychange", sichtbar);
  };
}

// Hell, dunkel oder wie das Gerät. Das wirksame Thema steht als data-theme auf
// <html>, die Wahl wird in localStorage gemerkt. Standard ist hell; "system"
// folgt der Einstellung des Geräts und wechselt mit ihr.

export type Thema = "hell" | "dunkel";
export type ThemaWahl = Thema | "system";

const SCHLUESSEL = "kw_thema";
const dunkelAbfrage = typeof matchMedia === "function" ? matchMedia("(prefers-color-scheme: dark)") : null;

function gemerkte(): ThemaWahl {
  let wert: string | null = null;
  try {
    wert = localStorage.getItem(SCHLUESSEL);
  } catch {
    // ohne Speicher gilt der Standard
  }
  return wert === "dunkel" || wert === "system" ? wert : "hell";
}

function wirksam(wahl: ThemaWahl): Thema {
  if (wahl !== "system") return wahl;
  return dunkelAbfrage?.matches ? "dunkel" : "hell";
}

const start = gemerkte();
export const thema = $state<{ wahl: ThemaWahl; aktuell: Thema }>({ wahl: start, aktuell: wirksam(start) });

export function themaAnwenden(): void {
  thema.aktuell = wirksam(thema.wahl);
  document.documentElement.dataset.theme = thema.aktuell;
}

dunkelAbfrage?.addEventListener("change", () => {
  if (thema.wahl === "system") themaAnwenden();
});

export function themaWaehlen(wahl: ThemaWahl): void {
  thema.wahl = wahl;
  try {
    localStorage.setItem(SCHLUESSEL, wahl);
  } catch {
    // Merken ist Komfort
  }
  themaAnwenden();
}

export function themaUmschalten(): void {
  themaWaehlen(thema.aktuell === "hell" ? "dunkel" : "hell");
}

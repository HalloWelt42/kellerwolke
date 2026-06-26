// Hell/dunkel-Umschaltung. Das gewaehlte Thema steht als data-theme auf <html>
// und wird in localStorage gemerkt. Standard ist hell.

export type Thema = "hell" | "dunkel";

const SCHLUESSEL = "kw_thema";

function gemerktes(): Thema {
  const wert = localStorage.getItem(SCHLUESSEL);
  return wert === "dunkel" ? "dunkel" : "hell";
}

export const thema = $state<{ aktuell: Thema }>({ aktuell: gemerktes() });

export function themaAnwenden(): void {
  document.documentElement.dataset.theme = thema.aktuell;
}

export function themaSetzen(neu: Thema): void {
  thema.aktuell = neu;
  localStorage.setItem(SCHLUESSEL, neu);
  themaAnwenden();
}

export function themaUmschalten(): void {
  themaSetzen(thema.aktuell === "hell" ? "dunkel" : "hell");
}

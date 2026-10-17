import type { Anfrage } from "./types";

// Stand einer Anfrage an eine App, kurz für die Zeile (Rechner und Telefon): Text (fällt bei schmaler Liste weg),
// Prozent (bleiben) und die ganze Erklärung für den Hinweis beim Überfahren.
export function anfrageStand(a: Anfrage): { text: string; zahl: string; titel: string; wartet: boolean } {
  if (a.zustand === "wartet" && !a.erreichbar) {
    return {
      text: `wartet auf ${a.app}`,
      zahl: "",
      titel: `${a.app} läuft gerade nicht; die Anfrage wartet und startet, sobald die App wieder da ist`,
      wartet: true,
    };
  }
  if (a.zustand === "wartet") return { text: `${a.titel} wartet`, zahl: "", titel: `${a.titel} mit ${a.app}`, wartet: true };
  const zahl = a.fortschritt != null ? `${Math.round(a.fortschritt * 100)} %` : "";
  return { text: a.titel, zahl, titel: `${a.titel} mit ${a.app}${a.meldung ? ": " + a.meldung : ""}`, wartet: false };
}

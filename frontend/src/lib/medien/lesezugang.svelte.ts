// Lesezugang heilen: Bilder, Vorschauen und Wiedergabe laden über ein Cookie, das an die Sitzung gebunden ist. Wird es
// ungültig (neue Sitzung in einem anderen Tab, Ablauf), kam bisher "Anmeldung abgelaufen - bitte neu anmelden", obwohl
// man angemeldet war. Jetzt richtet die Seite den Lesezugang beim ersten Fehler neu ein und lädt alle Inhalte über
// einen neuen Stand in der Adresse nach; erst wenn das nicht hilft, ist die Anmeldung wirklich abgelaufen.
import { lesezugangEinrichten } from "../api";

const MINDESTABSTAND_MS = 30_000;          // nie öfter erneuern, sonst Schleife bei echtem Fehler

export const lesezugang = $state({ stand: 0 });

let laufend: Promise<boolean> | null = null;
let zuletzt = 0;

/** Lesezugang neu einrichten; true, wenn es geklappt hat (dann laden die Inhalte mit neuem Stand neu). */
export function heilen(): Promise<boolean> {
  if (laufend) return laufend;
  if (Date.now() - zuletzt < MINDESTABSTAND_MS) return Promise.resolve(false);
  zuletzt = Date.now();
  laufend = lesezugangEinrichten()
    .then(() => {
      lesezugang.stand += 1;
      return true;
    })
    .catch(() => false)
    .finally(() => (laufend = null));
  return laufend;
}

/** Fehlgeschlagene Inhalte (auch Vorschaubilder ohne eigene Fehlerbehandlung) lösen das Heilen aus. */
export function heilenBeiFehlernBeobachten(): void {
  window.addEventListener(
    "error",
    (e) => {
      const ziel = e.target;
      if (ziel instanceof HTMLImageElement || ziel instanceof HTMLMediaElement) {
        if ((ziel.currentSrc || ziel.getAttribute("src") || "").includes("/api/v1/inhalt/")) void heilen();
      }
    },
    true,
  );
}

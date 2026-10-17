// Welche Ansicht der Hauptfläche zeigt: der Datei-Browser oder die
// Medienansicht. Fest im Kern, umgeschaltet über die Leiste unter dem Kopf.
// Die Medienansicht merkt sich ihre Einstellungen hier, damit ein Wechsel hin
// und zurück nichts verliert.
import type { Bereich } from "./browser.svelte";

export type HauptAnsicht = "dateien" | "medien";

export const ansicht = $state<{ aktiv: HauptAnsicht }>({ aktiv: "dateien" });

export function waehleAnsicht(a: HauptAnsicht): void {
  ansicht.aktiv = a;
}

// Wo die Medienansicht Sinn ergibt; anderswo ist ihr Knopf gesperrt.
export const MEDIEN_BEREICHE: Bereich[] = ["dateien", "favoriten", "geteilt"];

export type Medienquelle = "alle" | "ordner";
export type Medienfilter = "alle" | "bild" | "audio" | "video";
export type Mediendarstellung = "kacheln" | "liste";

export const medienEinstellung = $state<{
  quelle: Medienquelle;
  filter: Medienfilter;
  darstellung: Mediendarstellung;
}>({ quelle: "alle", filter: "alle", darstellung: "kacheln" });

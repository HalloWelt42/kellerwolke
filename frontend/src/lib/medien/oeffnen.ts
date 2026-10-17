// Medien öffnen, von überall gleich: Bilder und Videos in der zentralen
// Vollansicht (mit den Nachbarn der Ansicht), Audio in der Player-Leiste (mit
// den übrigen Titeln der Ansicht). "Zum Ordner" führt die aktive Fläche hin.
import { spielen, type Spur } from "../player.svelte";
import { oeffneVollansicht } from "../vorschau.svelte";
import { aktiveFlaeche } from "../zustand.svelte";
import { waehleAnsicht } from "../ansicht.svelte";
import type { Browser } from "../browser.svelte";
import type { Knoten, Pfadteil } from "../types";
import { ausKnoten, type MedienEintrag } from "./adressen";

export function alsSpur(m: MedienEintrag): Spur {
  return { id: m.id, etag: m.etag, titel: m.name, pfad: m.pfad };
}

// Öffnet liste[index]; liefert false, wenn es kein Medium ist.
export function medienOeffnen(liste: MedienEintrag[], index: number): boolean {
  const m = liste[index];
  if (!m) return false;
  if (m.art === "audio") {
    const audios = liste.filter((x) => x.art === "audio");
    spielen(audios.map(alsSpur), audios.findIndex((x) => x.id === m.id));
  } else {
    oeffneVollansicht(liste, index);
  }
  return true;
}

export function zumOrdner(pfad: Pfadteil[], markiereId?: string): void {
  waehleAnsicht("dateien");
  aktiveFlaeche().oeffnePfad(pfad, markiereId);
}

// Medien einer Fläche in ihrer sichtbaren Reihenfolge - die Nachbarn für
// Blättern und Titelliste. Die Ordnerkette ist nur in "Meine Dateien" bekannt.
export function medienDerFlaeche(b: Browser): MedienEintrag[] {
  const pfad = b.bereich === "dateien" ? b.pfad.slice(1) : null;
  const eigen = b.bereich !== "geteilt";
  return b.sichtbar.map((k) => ausKnoten(k, pfad, eigen)).filter((m): m is MedienEintrag => m !== null);
}

// Einen Knoten der Fläche als Medium öffnen; false, wenn er keins ist.
export function knotenOeffnen(b: Browser, k: Knoten): boolean {
  const liste = medienDerFlaeche(b);
  return medienOeffnen(liste, liste.findIndex((m) => m.id === k.id));
}

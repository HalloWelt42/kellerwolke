// Navigation der Telefon-Oberfläche: vier Reiter, Unterseiten (Suche, Geteilt,
// Papierkorb) und das eine Blatt von unten. Die Daten zeigt dieselbe Fläche wie
// am Rechner (haupt); hier steht nur, was das Telefon anders zeigt.
import { haupt } from "../zustand.svelte";
import type { Knoten, Pfadteil } from "../types";

export type MobilReiter = "dateien" | "medien" | "favoriten" | "mehr";
export type MobilSeite = "suche" | "geteilt" | "papierkorb";

// Was Halten-Bestätigung und Symbol von einem Eintrag brauchen (auch aus der Medienliste).
export type EintragKurz = Pick<Knoten, "id" | "name" | "typ" | "medienart">;

// Was das Blatt von unten gerade zeigt.
export type Blatt =
  | { art: "aktionen"; knoten: Knoten }
  | { art: "halten"; knoten: EintragKurz; was: "loeschen" | "endgueltig"; fertig?: () => void }
  | { art: "hochladen" }
  | { art: "umbenennen"; knoten: Knoten }
  | { art: "ordner" }
  | { art: "sortieren" }
  | { art: "thema" };

export const mobil = $state<{
  reiter: MobilReiter;
  seite: MobilSeite | null;
  blatt: Blatt | null;
  dateienPfad: Pfadteil[]; // zuletzt offener Ordner unter "Dateien" (ohne Wurzel)
}>({ reiter: "dateien", seite: null, blatt: null, dateienPfad: [] });

function dateienMerken(): void {
  if (haupt.bereich === "dateien") mobil.dateienPfad = haupt.pfad.slice(1);
}

export function zeigeReiter(reiter: MobilReiter): void {
  dateienMerken();
  mobil.blatt = null;
  mobil.seite = null;
  mobil.reiter = reiter;
  if (reiter === "dateien") {
    if (mobil.dateienPfad.length) haupt.oeffnePfad(mobil.dateienPfad);
    else haupt.zeigeDateien();
  } else if (reiter === "favoriten") {
    haupt.zeigeFavoriten();
  }
}

export function zeigeSeite(seite: MobilSeite): void {
  dateienMerken();
  mobil.blatt = null;
  mobil.seite = seite;
  if (seite === "geteilt") haupt.zeigeGeteilt();
  else if (seite === "papierkorb") haupt.zeigePapierkorb();
}

export function sucheBeenden(): void {
  mobil.seite = null;
  zeigeReiter(mobil.reiter);
}

// Eine Ebene zurück: Ordner hoch, Unterseite schließen.
export function zurueck(): void {
  if (mobil.seite === "geteilt" && haupt.geteiltPfad.length) {
    haupt.geteiltBreadcrumb(haupt.geteiltPfad.length - 2);
  } else if (mobil.seite) {
    mobil.seite = null;
    zeigeReiter(mobil.reiter);
  } else if (haupt.bereich === "dateien" && haupt.pfad.length > 1) {
    haupt.breadcrumbGehe(haupt.pfad.length - 2);
  }
}

export function blattOeffnen(b: Blatt): void {
  mobil.blatt = b;
}

export function blattSchliessen(): void {
  mobil.blatt = null;
}

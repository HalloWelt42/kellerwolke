import type { Knoten } from "./types";

// Arten von Einträgen an einer Stelle (KW-10). Ein Verweis zeigt auf eine Datei und liest deren Inhalt; verwaist hat
// er keinen. Wer prüft, ob etwas wie eine Datei in der Liste steht oder ob es Inhalt liefert, fragt hier.

export function istVerweis(k: Knoten): boolean {
  return k.typ === "verweis";
}

// Steht wie eine Datei in der Liste (bei den Dateien, nach Art gefiltert): Dateien und Verweise.
export function istDateiartig(k: Knoten): boolean {
  return k.typ === "datei" || k.typ === "verweis";
}

// Liefert Inhalt (Vorschau, Wiedergabe, Herunterladen): eine Datei oder ein Verweis mit lebendem Original.
export function liestInhalt(k: Knoten): boolean {
  return k.typ === "datei" || (k.typ === "verweis" && !k.verwaist);
}

export function verweiseText(n: number): string {
  return n === 1 ? "1 Verweis" : `${n} Verweise`;
}

export function mitVerweisen(n: number): string {
  return n === 1 ? "mit 1 Verweis" : `mit ${n} Verweisen`;
}

// Pfad für die Anzeige ("Apps/Telegram/2026-11"); die oberste Ebene heißt "Meine Dateien".
export function ortText(ort: string): string {
  return ort || "Meine Dateien";
}

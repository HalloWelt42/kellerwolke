// Multipler Datei-Filter: mehrere Regeln, jede mit eigenem Modus (einzelne
// Woerter / ganzer Satz / Regex), Gross-/Kleinschreibung und Negation. Die
// Regeln werden per UND (Standard: einengen) oder ODER (erweitern) verknuepft.
// Reine Funktionen ohne Runes - leicht testbar, von jeder Browsing-Instanz
// geteilt.

import { eindeutigeId } from "./id";

export type FilterModus = "woerter" | "satz" | "regex";

export interface Filterregel {
  id: string;
  text: string;
  modus: FilterModus;
  caseSensitive: boolean;
  negiert: boolean; // "enthaelt NICHT"
}

export interface Filterzustand {
  regeln: Filterregel[];
  verknuepfung: "und" | "oder";
}

export function leereRegel(): Filterregel {
  return { id: eindeutigeId(), text: "", modus: "woerter", caseSensitive: false, negiert: false };
}

export function leererFilter(): Filterzustand {
  return { regeln: [leereRegel()], verknuepfung: "und" };
}

// Mindestens eine Regel hat Text -> der Filter greift ueberhaupt.
export function filterAktiv(f: Filterzustand): boolean {
  return f.regeln.some((r) => r.text.trim() !== "");
}

function baueRegex(text: string, caseSensitive: boolean): RegExp | null {
  try {
    return new RegExp(text, caseSensitive ? "" : "i");
  } catch {
    return null;
  }
}

// Fuer die UI: ist die Regel (insbesondere eine Regex) gueltig?
export function regelGueltig(r: Filterregel): boolean {
  if (r.modus !== "regex" || r.text.trim() === "") return true;
  return baueRegex(r.text, r.caseSensitive) !== null;
}

function regelPasst(name: string, r: Filterregel): boolean {
  const text = r.text.trim();
  if (text === "") return true; // leere Regel filtert nicht
  let treffer: boolean;
  if (r.modus === "regex") {
    const re = baueRegex(text, r.caseSensitive);
    treffer = re ? re.test(name) : false; // ungueltige Regex trifft nie
  } else {
    const n = r.caseSensitive ? name : name.toLowerCase();
    const t = r.caseSensitive ? text : text.toLowerCase();
    if (r.modus === "satz") {
      treffer = n.includes(t); // ganzer Text als zusammenhaengender Teilstring
    } else {
      // woerter: alle durch Leerzeichen getrennten Tokens muessen vorkommen
      treffer = t.split(/\s+/).filter(Boolean).every((tok) => n.includes(tok));
    }
  }
  return r.negiert ? !treffer : treffer;
}

export function passt(name: string, f: Filterzustand): boolean {
  const aktive = f.regeln.filter((r) => r.text.trim() !== "");
  if (aktive.length === 0) return true;
  const treffer = aktive.map((r) => regelPasst(name, r));
  return f.verknuepfung === "und" ? treffer.every(Boolean) : treffer.some(Boolean);
}

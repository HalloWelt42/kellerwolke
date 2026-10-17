import type { Knoten } from "./types";

// Reine Hilfsfunktionen für Anzeige: Größe, Datum und Dateisymbole.

export function groesseText(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  return `${(bytes / 1024 / 1024 / 1024).toFixed(1)} GB`;
}

// Restzeit grob als "noch ca. ..." (Sekunden < 0 = unbekannt).
export function zeitText(sekunden: number): string {
  if (sekunden < 0) return "";
  if (sekunden < 60) return `noch ca. ${Math.max(1, Math.round(sekunden))} Sek`;
  if (sekunden < 3600) return `noch ca. ${Math.round(sekunden / 60)} Min`;
  return `noch ca. ${Math.round(sekunden / 3600)} Std`;
}

export function datum(iso: string): string {
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "-";
  return d.toLocaleString("de-DE", { dateStyle: "medium", timeStyle: "short" });
}

const NACH_ENDUNG: Record<string, string> = {
  pdf: "fa-file-pdf",
  doc: "fa-file-word",
  docx: "fa-file-word",
  odt: "fa-file-word",
  xls: "fa-file-excel",
  xlsx: "fa-file-excel",
  ods: "fa-file-excel",
  csv: "fa-file-csv",
  ppt: "fa-file-powerpoint",
  pptx: "fa-file-powerpoint",
  txt: "fa-file-lines",
  md: "fa-file-lines",
  rtf: "fa-file-lines",
  jpg: "fa-file-image",
  jpeg: "fa-file-image",
  png: "fa-file-image",
  gif: "fa-file-image",
  webp: "fa-file-image",
  heic: "fa-file-image",
  svg: "fa-file-image",
  zip: "fa-file-zipper",
  rar: "fa-file-zipper",
  "7z": "fa-file-zipper",
  tar: "fa-file-zipper",
  gz: "fa-file-zipper",
  mp3: "fa-file-audio",
  wav: "fa-file-audio",
  flac: "fa-file-audio",
  mp4: "fa-file-video",
  mov: "fa-file-video",
  mkv: "fa-file-video",
  webm: "fa-file-video",
};

export function symbolFuerName(name: string): string {
  const punkt = name.lastIndexOf(".");
  if (punkt > 0) {
    const endung = name.slice(punkt + 1).toLowerCase();
    if (NACH_ENDUNG[endung]) return NACH_ENDUNG[endung];
  }
  return "fa-file";
}

// Medienart bestimmt der Server (eine Stelle für alle Endungen, auch m4a, ogg, opus); die Rolle eines Begleiters
// geht vor (ein Transkript ist eine JSON-Datei, zeigt sich aber als Untertitelsymbol).
const NACH_MEDIENART: Record<string, string> = { bild: "fa-file-image", audio: "fa-file-audio", video: "fa-file-video" };
const NACH_ROLLE: Record<string, string> = {
  transkript: "fa-closed-captioning", untertitel: "fa-closed-captioning", untertitel_vtt: "fa-closed-captioning",
  protokoll: "fa-list-check", zusammenfassung: "fa-list-check", aufgaben: "fa-list-check", sprache: "fa-volume-high",
};

// Symbol der Rolle eines Begleiters, wenn sie eins hat (Rechner und Telefon).
export function rollenSymbol(rolle: string | null | undefined): string | null {
  return (rolle && NACH_ROLLE[rolle]) || null;
}

// Liefert das Font-Awesome-Symbol und ob es die Sonderfarbe (Ordner/Extern) trägt.
export function symbol(k: Knoten): { icon: string; klasse: string } {
  if (k.typ === "ordner") return { icon: "fa-folder", klasse: "ordner" };
  if (k.typ === "extern") return { icon: "fa-folder-tree", klasse: "extern" };
  const icon = rollenSymbol(k.rolle) || (k.medienart && NACH_MEDIENART[k.medienart]) || symbolFuerName(k.name);
  return { icon, klasse: "" };
}

// Anzeigename der Rolle eines Begleiters (die Rollen der eigenen Apps; unbekannte lesbar aus dem Schlüssel).
const ROLLEN: Record<string, string> = {
  transkript: "Transkript", untertitel: "Untertitel", untertitel_vtt: "Untertitel (WebVTT)", text: "Text",
  markdown: "Markdown", daten: "Daten", dokument: "Dokument", protokoll: "Protokoll", zusammenfassung: "Zusammenfassung",
  aufgaben: "Aufgaben", sprache: "Sprachausgabe",
};
export function rolleText(rolle: string): string {
  return ROLLEN[rolle] ?? rolle.charAt(0).toUpperCase() + rolle.slice(1).replaceAll("_", " ");
}

export function begleiterText(n: number): string {
  return n === 1 ? "1 Begleiter" : `${n} Begleiter`;
}

export function mitBegleitern(n: number): string {
  return n === 1 ? "mit 1 Begleiter" : `mit ${n} Begleitern`;
}

const TYP_NACH_ENDUNG: Record<string, string> = {
  pdf: "PDF-Dokument",
  doc: "Textdokument",
  docx: "Textdokument",
  odt: "Textdokument",
  rtf: "Textdokument",
  txt: "Textdatei",
  md: "Textdatei",
  xls: "Tabelle",
  xlsx: "Tabelle",
  ods: "Tabelle",
  csv: "Tabelle",
  ppt: "Präsentation",
  pptx: "Präsentation",
  jpg: "Bild",
  jpeg: "Bild",
  png: "Bild",
  gif: "Bild",
  webp: "Bild",
  heic: "Bild",
  svg: "Bild",
  zip: "Archiv",
  rar: "Archiv",
  "7z": "Archiv",
  tar: "Archiv",
  gz: "Archiv",
  mp3: "Audio",
  wav: "Audio",
  flac: "Audio",
  mp4: "Video",
  mov: "Video",
  mkv: "Video",
  webm: "Video",
};

export function typLabel(k: Knoten): string {
  if (k.typ === "ordner") return "Ordner";
  if (k.typ === "extern") return "Externe Quelle";
  const punkt = k.name.lastIndexOf(".");
  if (punkt > 0) {
    const endung = k.name.slice(punkt + 1).toLowerCase();
    if (TYP_NACH_ENDUNG[endung]) return TYP_NACH_ENDUNG[endung];
  }
  return "Datei";
}

// Inhalt eines Ordners für Zeile und Kachel: zählt Dateien und Unterordner.
export function ordnerInhalt(anzahl: number | null | undefined, unbekannt = "Ordner"): string {
  if (anzahl == null) return unbekannt;
  if (anzahl === 0) return "Leer";
  return anzahl === 1 ? "1 Eintrag" : `${anzahl} Einträge`;
}

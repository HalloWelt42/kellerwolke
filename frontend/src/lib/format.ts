import type { Knoten } from "./types";

// Reine Hilfsfunktionen fuer Anzeige: Groesse, Datum und Dateisymbole.

export function groesseText(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  return `${(bytes / 1024 / 1024 / 1024).toFixed(1)} GB`;
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

// Liefert das Font-Awesome-Symbol und ob es die Sonderfarbe (Ordner/Extern) traegt.
export function symbol(k: Knoten): { icon: string; klasse: string } {
  if (k.typ === "ordner") return { icon: "fa-folder", klasse: "ordner" };
  if (k.typ === "extern") return { icon: "fa-folder-tree", klasse: "extern" };
  return { icon: symbolFuerName(k.name), klasse: "" };
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

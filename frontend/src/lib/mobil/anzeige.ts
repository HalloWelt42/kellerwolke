import { groesseText, ordnerInhalt, rollenSymbol, symbolFuerName } from "../format";
import type { Knoten } from "../types";

// Symbol und Farbe einer Zeile am Telefon.
export function mSymbol(k: Pick<Knoten, "typ" | "name" | "medienart" | "rolle">): { icon: string; klasse: string } {
  if (k.typ === "ordner") return { icon: "fa-folder", klasse: "ordner" };
  if (k.typ === "extern") return { icon: "fa-folder-tree", klasse: "ordner" };
  const rolle = rollenSymbol(k.rolle);
  if (rolle) return { icon: rolle, klasse: "" };
  const art = k.medienart;
  if (art === "bild") return { icon: "fa-file-image", klasse: "bild" };
  if (art === "audio") return { icon: "fa-file-audio", klasse: "ton" };
  if (art === "video") return { icon: "fa-file-video", klasse: "video" };
  const icon = symbolFuerName(k.name);
  return { icon, klasse: icon === "fa-file-pdf" ? "pdf" : "" };
}

// Kurzes Datum: "heute, 09:14", "gestern" oder "12.10.2026".
export function kurzDatum(iso: string): string {
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "";
  const heute = new Date();
  const tag = (x: Date) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const abstand = Math.round((tag(heute) - tag(d)) / 86400000);
  if (abstand === 0) return `heute, ${d.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" })}`;
  if (abstand === 1) return "gestern";
  return d.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric" });
}

// Zweite Zeile unter dem Namen.
export function zeilenMeta(k: Knoten, imPapierkorb: boolean): string {
  if (k.typ === "ordner") return imPapierkorb ? `gelöscht ${kurzDatum(k.geaendert_am)}` : ordnerInhalt(k.kinder_anzahl, "Ordner");
  if (k.typ === "extern") return "Externe Quelle";
  const teile = [k.groesse != null ? groesseText(k.groesse).replace(".", ",") : "", kurzDatum(k.geaendert_am)].filter(Boolean);
  return (imPapierkorb ? "gelöscht " : "") + teile.join(" · ");
}

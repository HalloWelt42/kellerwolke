import type { Knoten, Medienart, Medium, Pfadteil } from "../types";
import { heilen, lesezugang } from "./lesezugang.svelte";

// Ein Medium, wie es Vollansicht, Player und Medienansicht kennen - gebaut aus
// einem Knoten der Dateiliste oder einem Eintrag der Medienliste.
export interface MedienEintrag {
  id: string;
  name: string;
  etag: string | null;
  art: Medienart;
  groesse: number | null;
  pfad: Pfadteil[] | null; // Ordnerkette ohne "Meine Dateien"; null = unbekannt (kein "Zum Ordner")
  geaendert_am: string | null;
  favorit: boolean | null; // null = unbekannt (dann kein Stern)
  eigen: boolean; // eigene Datei: favorisieren und löschen möglich
}

export function ausKnoten(k: Knoten, pfad: Pfadteil[] | null, eigen = true): MedienEintrag | null {
  if (k.typ !== "datei" || !k.medienart) return null;
  return {
    id: k.id, name: k.name, etag: k.etag, art: k.medienart, groesse: k.groesse ?? null, pfad,
    geaendert_am: k.geaendert_am, favorit: eigen ? !!k.favorit : null, eigen,
  };
}

export function ausMedium(m: Medium): MedienEintrag {
  return {
    id: m.id, name: m.name, etag: m.etag, art: m.art, groesse: m.groesse, pfad: m.pfad,
    geaendert_am: m.geaendert_am, favorit: null, eigen: true,
  };
}

// Adressen des Lesezugangs (Cookie, siehe api.lesezugangEinrichten). Der
// Versionsstand in der Adresse erlaubt dauerhaftes Zwischenspeichern; nach einer
// neuen Version lautet die Adresse anders.
function stand(etag: string | null): string {
  const teile = [etag ? `v=${encodeURIComponent(etag)}` : "", lesezugang.stand ? `z=${lesezugang.stand}` : ""];
  return teile.filter(Boolean).join("&");
}

export type Stufe = "klein" | "gross";

export function vorschauUrl(m: { id: string; etag: string | null }, stufe: Stufe = "gross"): string {
  const v = stand(m.etag);
  return `/api/v1/inhalt/vorschau/${m.id}?stufe=${stufe}${v ? `&${v}` : ""}`;
}

export function vollUrl(m: { id: string; etag: string | null }): string {
  const v = stand(m.etag);
  return `/api/v1/inhalt/voll/${m.id}${v ? `?${v}` : ""}`;
}

export function stromUrl(m: { id: string; etag: string | null }): string {
  const v = stand(m.etag);
  return `/api/v1/inhalt/strom/${m.id}${v ? `?${v}` : ""}`;
}

export function formatKuerzel(name: string): string {
  const p = name.lastIndexOf(".");
  return p > 0 ? name.slice(p + 1).toUpperCase() : "";
}

// Warum ein Bild, Titel oder Video nicht kam: das Medienelement meldet nur
// "Fehler", der Server weiss mehr. Fragt ein einziges Byte ab und übersetzt.
export async function ursache(url: string): Promise<string> {
  try {
    const r = await fetch(url, { headers: { Range: "bytes=0-0" } });
    if (r.status === 401) return (await heilen()) ? "" : "Anmeldung abgelaufen - bitte neu anmelden";
    if (r.status === 404) return "Die Datei gibt es nicht mehr";
    if (r.status === 415) return "Der Inhalt lässt sich nicht darstellen";
    if (r.status === 503) return "Der Speicher ist gerade nicht erreichbar";
    if (r.ok) return "Dieses Format spielt der Browser nicht ab (sicher gehen mp3, mp4 mit H.264 und webm)";
    return `Fehler ${r.status}`;
  } catch {
    return "Keine Verbindung zum Server";
  }
}

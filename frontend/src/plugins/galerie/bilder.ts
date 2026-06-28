import { token } from "../../lib/api";

// Bild-Erkennung + URLs zu den Galerie-Backend-Endpunkten. Auth per Query-Token,
// weil <img src> keine Header setzen kann.

const BILD_ENDUNGEN = [".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".heic", ".heif", ".svg"];

export function istBild(name: string): boolean {
  const p = name.lastIndexOf(".");
  return p !== -1 && BILD_ENDUNGEN.includes(name.slice(p).toLowerCase());
}

export function thumbUrl(id: string, kante: number): string {
  return `/api/v1/plugins/galerie/thumb/${id}?kante=${kante}&t=${encodeURIComponent(token())}`;
}

export function inlineUrl(id: string): string {
  return `/api/v1/plugins/galerie/inline/${id}?t=${encodeURIComponent(token())}`;
}

// Ein Bild in der zentralen (baumweiten) Galerieansicht: Datei plus Ordnerkette.
export interface GBild {
  id: string;
  name: string;
  groesse: number | null;
  pfad: { id: string; name: string }[]; // Ordner von der Wurzel bis zum Elternordner
}

// Alle Bilder des Nutzers ueber alle Ordner. Header-Token (kein <img>, daher kein ?t=).
export async function ladeAlleBilder(): Promise<GBild[]> {
  const antwort = await fetch("/api/v1/plugins/galerie/alle", {
    headers: { "X-Kellerwolke-Sitzung": token() },
  });
  if (!antwort.ok) throw new Error("Galerie konnte nicht geladen werden");
  return antwort.json();
}

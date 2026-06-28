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

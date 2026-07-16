import { token } from "../../lib/api";

// Erkennung + URLs zu den Medien-Endpunkten. Auth per Query-Token, weil
// <img>/<audio> keine Header setzen koennen.
const BILD = [".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".heic", ".heif", ".svg"];
const AUDIO = [".mp3", ".wav", ".ogg", ".oga", ".opus", ".m4a", ".aac", ".flac"];
// Video laeuft ueber denselben Stream-Endpunkt wie Audio (HTTP-Range).
const VIDEO = [".mp4", ".m4v", ".mov", ".webm", ".mkv", ".ogv"];

function endung(name: string): string {
  const p = name.lastIndexOf(".");
  return p === -1 ? "" : name.slice(p).toLowerCase();
}
export function istBild(name: string): boolean { return BILD.includes(endung(name)); }
export function istAudio(name: string): boolean { return AUDIO.includes(endung(name)); }
export function istVideo(name: string): boolean { return VIDEO.includes(endung(name)); }
export function formatKuerzel(name: string): string { return endung(name).replace(".", "").toUpperCase(); }

const t = () => encodeURIComponent(token());
export function thumbUrl(id: string, kante: number): string { return `/api/v1/plugins/medien/thumb/${id}?kante=${kante}&t=${t()}`; }
export function inlineUrl(id: string): string { return `/api/v1/plugins/medien/inline/${id}?t=${t()}`; }
export function streamUrl(id: string): string { return `/api/v1/plugins/medien/stream/${id}?t=${t()}`; }

export interface GMedium {
  id: string;
  name: string;
  groesse: number | null;
  pfad: { id: string; name: string }[];
  typ: "bild" | "audio" | "video";
}

export async function ladeAlleMedien(): Promise<GMedium[]> {
  const r = await fetch("/api/v1/plugins/medien/alle", { headers: { "X-Kellerwolke-Sitzung": token() } });
  if (!r.ok) throw new Error("Medien konnten nicht geladen werden");
  return r.json();
}

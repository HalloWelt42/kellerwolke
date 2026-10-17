import * as api from "../api";
import type { Knoten } from "../types";

// Über das Teilen-Menü des Telefons weitergeben (Nachricht, Fotos, Dateien-App).
// Das geht nur im sicheren Kontext (HTTPS) und für Dateien, die in den Speicher
// des Telefons passen; sonst wird ganz normal heruntergeladen.
const GRENZE = 100 * 1024 * 1024;

export function kannTeilen(): boolean {
  return typeof navigator.share === "function" && typeof navigator.canShare === "function";
}

export async function teilenOderSichern(k: Knoten): Promise<void> {
  if (kannTeilen() && (k.groesse ?? 0) <= GRENZE) {
    try {
      const antwort = await fetch(`/api/v1/inhalt/datei/${k.id}`);
      if (antwort.ok) {
        const blob = await antwort.blob();
        const datei = new File([blob], k.name, { type: blob.type || "application/octet-stream" });
        if (navigator.canShare({ files: [datei] })) {
          await navigator.share({ files: [datei], title: k.name });
          return;
        }
      }
    } catch (f) {
      if ((f as Error).name === "AbortError") return; // im Menü abgebrochen
    }
  }
  api.herunterladen(k);
}

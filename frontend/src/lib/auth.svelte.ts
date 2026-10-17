import * as api from "./api";
import { playerZuruecksetzen } from "./player.svelte";
import { kontoVerlassen } from "./zustand.svelte";
import { schliesseVollansicht } from "./vorschau.svelte";
import { waehleAnsicht } from "./ansicht.svelte";
import type { Benutzer } from "./types";

export const auth = $state<{
  geladen: boolean;
  angemeldet: boolean;
  benutzer: Benutzer | null;
}>({
  geladen: false,
  angemeldet: false,
  benutzer: null,
});

// Endet die Sitzung auf dem Server (abgelaufen, gesperrt, anderswo abgemeldet),
// zeigt die Oberfläche wieder die Anmeldung - wie nach einem Abmelden.
api.sitzungsendeMelden(() => {
  if (auth.angemeldet) aufraeumen();
});

// Abmelden heisst: nichts vom Konto bleibt im Browser zurück.
function aufraeumen(): void {
  playerZuruecksetzen();
  schliesseVollansicht();
  kontoVerlassen();
  waehleAnsicht("dateien");
  api.lesezugangBeenden();
  auth.angemeldet = false;
  auth.benutzer = null;
}

async function zugangEinrichten(): Promise<void> {
  try {
    await api.lesezugangEinrichten();
  } catch {
    // ohne Lesezugang fehlen nur Vorschauen und Wiedergabe; die Meldung kommt dort
  }
}

export async function ladeStatus(): Promise<void> {
  try {
    const s = await api.status();
    if (s.angemeldet) await zugangEinrichten();
    auth.benutzer = s.benutzer ?? null;
    auth.angemeldet = s.angemeldet;
  } catch {
    auth.angemeldet = false;
    auth.benutzer = null;
  } finally {
    auth.geladen = true;
  }
}

export async function anmelden(kennung: string, passwort: string): Promise<void> {
  const benutzer = await api.anmelden(kennung, passwort);
  await zugangEinrichten();
  auth.benutzer = benutzer;
  auth.angemeldet = true;
}

export async function abmelden(): Promise<void> {
  await api.abmelden();
  aufraeumen();
}

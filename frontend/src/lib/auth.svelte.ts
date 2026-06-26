import * as api from "./api";
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

export async function ladeStatus(): Promise<void> {
  try {
    const s = await api.status();
    auth.angemeldet = s.angemeldet;
    auth.benutzer = s.benutzer ?? null;
  } catch {
    auth.angemeldet = false;
    auth.benutzer = null;
  } finally {
    auth.geladen = true;
  }
}

export async function anmelden(kennung: string, passwort: string): Promise<void> {
  const benutzer = await api.anmelden(kennung, passwort);
  auth.angemeldet = true;
  auth.benutzer = benutzer;
}

export async function abmelden(): Promise<void> {
  await api.abmelden();
  auth.angemeldet = false;
  auth.benutzer = null;
}

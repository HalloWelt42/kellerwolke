import type { AuthStatus, Benutzer, ExternEintrag, Knoten, SpeicherStatus, Version } from "./types";

// Sitzungs-Token im localStorage und im Header (kein Cookie). Bewusste Wahl fuer
// eine lokale Familien-Cloud: einfache, CSRF-unempfindliche Header-Authentifizierung.
// Das Frontend nutzt nirgends @html, die XSS-Flaeche ist entsprechend klein.
const SCHLUESSEL = "kw_sitzung";

export class ApiFehler extends Error {
  status: number;
  constructor(status: number, nachricht: string) {
    super(nachricht);
    this.status = status;
  }
}

export function token(): string {
  return localStorage.getItem(SCHLUESSEL) ?? "";
}

export function setzeToken(wert: string): void {
  if (wert) localStorage.setItem(SCHLUESSEL, wert);
  else localStorage.removeItem(SCHLUESSEL);
}

async function pruefe(antwort: Response): Promise<Response> {
  if (antwort.status === 401) {
    setzeToken("");
    throw new ApiFehler(401, "Anmeldung erforderlich");
  }
  if (!antwort.ok) {
    let text = antwort.statusText;
    try {
      const daten = await antwort.json();
      text = daten.detail ?? text;
    } catch {
      // Text bleibt
    }
    throw new ApiFehler(antwort.status, text);
  }
  return antwort;
}

async function hole<T>(pfad: string, init: RequestInit = {}): Promise<T> {
  const antwort = await fetch(`/api${pfad}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-Kellerwolke-Sitzung": token(),
      ...(init.headers ?? {}),
    },
  });
  await pruefe(antwort);
  if (antwort.status === 204) return undefined as T;
  return (await antwort.json()) as T;
}

// --- Auth -------------------------------------------------------------------

export async function anmelden(kennung: string, passwort: string): Promise<Benutzer> {
  const daten = await hole<{ token: string; benutzer: Benutzer }>("/v1/auth/login", {
    method: "POST",
    body: JSON.stringify({ kennung, passwort }),
  });
  setzeToken(daten.token);
  return daten.benutzer;
}

export async function abmelden(): Promise<void> {
  try {
    await hole("/v1/auth/logout", { method: "POST" });
  } catch {
    // egal
  }
  setzeToken("");
}

export function status(): Promise<AuthStatus> {
  return hole<AuthStatus>("/v1/auth/status");
}

export async function version(): Promise<string> {
  const daten = await hole<{ version: string }>("/health");
  return daten.version;
}

// --- Dateien ----------------------------------------------------------------

export function kinder(parentId: string | null): Promise<Knoten[]> {
  const frage = parentId ? `?parent_id=${parentId}` : "";
  return hole<Knoten[]>(`/v1/dateien${frage}`);
}

export function papierkorb(): Promise<Knoten[]> {
  return hole<Knoten[]>("/v1/dateien/papierkorb");
}

export function papierkorbLeeren(): Promise<void> {
  return hole<void>("/v1/dateien/papierkorb", { method: "DELETE" });
}

export function speicherStatus(): Promise<SpeicherStatus> {
  return hole<SpeicherStatus>("/v1/dateien/speicher-status");
}

export function ordnerAnlegen(name: string, parentId: string | null): Promise<Knoten> {
  return hole<Knoten>("/v1/dateien/ordner", {
    method: "POST",
    body: JSON.stringify({ name, parent_id: parentId }),
  });
}

export async function hochladen(datei: File, parentId: string | null): Promise<Knoten> {
  const formular = new FormData();
  formular.append("datei", datei);
  if (parentId) formular.append("parent_id", parentId);
  const antwort = await fetch("/api/v1/dateien/upload", {
    method: "POST",
    headers: { "X-Kellerwolke-Sitzung": token() },
    body: formular,
  });
  await pruefe(antwort);
  return (await antwort.json()) as Knoten;
}

export async function herunterladen(knoten: Knoten): Promise<void> {
  const antwort = await fetch(`/api/v1/dateien/${knoten.id}/inhalt`, {
    headers: { "X-Kellerwolke-Sitzung": token() },
  });
  await pruefe(antwort);
  const blob = await antwort.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = knoten.name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export function umbenennen(id: string, name: string): Promise<Knoten> {
  return hole<Knoten>(`/v1/dateien/${id}/name`, {
    method: "PATCH",
    body: JSON.stringify({ name }),
  });
}

export function verschieben(id: string, parentId: string | null): Promise<Knoten> {
  return hole<Knoten>(`/v1/dateien/${id}/ort`, {
    method: "PATCH",
    body: JSON.stringify({ parent_id: parentId }),
  });
}

export function loeschen(id: string): Promise<void> {
  return hole<void>(`/v1/dateien/${id}`, { method: "DELETE" });
}

export function wiederherstellen(id: string): Promise<Knoten> {
  return hole<Knoten>(`/v1/dateien/${id}/wiederherstellen`, { method: "POST" });
}

export function versionen(id: string): Promise<Version[]> {
  return hole<Version[]>(`/v1/dateien/${id}/versionen`);
}

// --- Suche ------------------------------------------------------------------

export function suchen(q: string): Promise<Knoten[]> {
  return hole<Knoten[]>(`/v1/suche?q=${encodeURIComponent(q)}`);
}

// --- Externe Quellen (read-only) --------------------------------------------

export function externAuflisten(knotenId: string, unterpfad: string): Promise<ExternEintrag[]> {
  return hole<ExternEintrag[]>(
    `/v1/dateien/extern/${knotenId}?unterpfad=${encodeURIComponent(unterpfad)}`,
  );
}

export async function externHerunterladen(
  knotenId: string,
  unterpfad: string,
  name: string,
): Promise<void> {
  const antwort = await fetch(
    `/api/v1/dateien/extern/${knotenId}/inhalt?unterpfad=${encodeURIComponent(unterpfad)}`,
    { headers: { "X-Kellerwolke-Sitzung": token() } },
  );
  await pruefe(antwort);
  const blob = await antwort.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

// --- Admin ------------------------------------------------------------------

export function listeBenutzer(): Promise<Benutzer[]> {
  return hole<Benutzer[]>("/v1/admin/benutzer");
}

export function benutzerAnlegen(
  name: string,
  passwort: string,
  rolle: string,
  kuerzel?: string,
): Promise<Benutzer> {
  return hole<Benutzer>("/v1/admin/benutzer", {
    method: "POST",
    body: JSON.stringify({ name, passwort, rolle, kuerzel: kuerzel || null }),
  });
}

export function benutzerAktualisieren(
  id: string,
  aenderung: { aktiv?: boolean; quota_bytes?: number | null; rolle?: string },
): Promise<void> {
  return hole<void>(`/v1/admin/benutzer/${id}`, {
    method: "PATCH",
    body: JSON.stringify(aenderung),
  });
}

export function externeQuelleAnlegen(
  besitzerId: string,
  name: string,
  pfad: string,
): Promise<Knoten> {
  return hole<Knoten>("/v1/admin/externe-quelle", {
    method: "POST",
    body: JSON.stringify({ besitzer_id: besitzerId, name, pfad }),
  });
}

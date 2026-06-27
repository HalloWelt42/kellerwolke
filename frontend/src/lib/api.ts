import type {
  AuthStatus,
  Benutzer,
  ExternEintrag,
  Freigabe,
  Knoten,
  Konto,
  SpeicherStatus,
  Verschiebung,
  Version,
  Vorgang,
} from "./types";

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

// Aenderungs-Journal des Nutzers ab einer Sequenznummer (fuer Live-Abgleich).
export function journalSeit(seit: number): Promise<{ seq: number }[]> {
  return hole<{ seq: number }[]>(`/v1/sync/journal?seit=${seit}`);
}

// --- Dateien ----------------------------------------------------------------

export function kinder(parentId: string | null): Promise<Knoten[]> {
  const frage = parentId ? `?parent_id=${parentId}` : "";
  return hole<Knoten[]>(`/v1/dateien${frage}`);
}

export function papierkorb(): Promise<Knoten[]> {
  return hole<Knoten[]>("/v1/dateien/papierkorb");
}

export function favoriten(): Promise<Knoten[]> {
  return hole<Knoten[]>("/v1/dateien/favoriten");
}

export function favoritSetzen(id: string, an: boolean): Promise<void> {
  return hole<void>(`/v1/dateien/${id}/favorit`, { method: an ? "POST" : "DELETE" });
}

// --- Geteilt ----------------------------------------------------------------

export function konten(): Promise<Konto[]> {
  return hole<Konto[]>("/v1/dateien/konten");
}

export function teilen(id: string, zielBenutzerId: string, rechte: string): Promise<void> {
  return hole<void>(`/v1/dateien/${id}/teilen`, {
    method: "POST",
    body: JSON.stringify({ ziel_benutzer_id: zielBenutzerId, rechte }),
  });
}

export function teilenEntfernen(id: string, zielId: string): Promise<void> {
  return hole<void>(`/v1/dateien/${id}/teilen/${zielId}`, { method: "DELETE" });
}

export function freigaben(id: string): Promise<Freigabe[]> {
  return hole<Freigabe[]>(`/v1/dateien/${id}/freigaben`);
}

export function geteilt(): Promise<Knoten[]> {
  return hole<Knoten[]>("/v1/dateien/geteilt");
}

export function geteiltKinder(id: string): Promise<Knoten[]> {
  return hole<Knoten[]>(`/v1/dateien/geteilt/${id}`);
}

export async function geteiltHerunterladen(knoten: Knoten): Promise<void> {
  const antwort = await fetch(`/api/v1/dateien/geteilt/${knoten.id}/inhalt`, {
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

export function papierkorbLeeren(): Promise<void> {
  return hole<void>("/v1/dateien/papierkorb", { method: "DELETE" });
}

export function speicherStatus(): Promise<SpeicherStatus> {
  return hole<SpeicherStatus>("/v1/dateien/speicher-status");
}

export function vorgaenge(): Promise<Vorgang[]> {
  return hole<Vorgang[]>("/v1/vorgaenge");
}

export function vorgangAbbrechen(id: string): Promise<void> {
  return hole<void>(`/v1/vorgaenge/${id}/abbrechen`, { method: "POST" });
}

export function vorgaengeAufraeumen(): Promise<void> {
  return hole<void>("/v1/vorgaenge/aufraeumen", { method: "POST" });
}

export function ordnerAnlegen(name: string, parentId: string | null): Promise<Knoten> {
  return hole<Knoten>("/v1/dateien/ordner", {
    method: "POST",
    body: JSON.stringify({ name, parent_id: parentId }),
  });
}

export interface UploadGriff {
  abbrechen: () => void;
}

// Upload ueber XMLHttpRequest, damit der echte Sende-Fortschritt verfolgt und
// abgebrochen werden kann (fetch liefert keinen Upload-Fortschritt).
export function hochladen(
  datei: File,
  parentId: string | null,
  aufFortschritt?: (geladen: number, gesamt: number) => void,
  griffSetzen?: (griff: UploadGriff) => void,
): Promise<Knoten> {
  return new Promise<Knoten>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/v1/dateien/upload");
    xhr.setRequestHeader("X-Kellerwolke-Sitzung", token());
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) aufFortschritt?.(e.loaded, e.total);
    };
    xhr.onload = () => {
      if (xhr.status === 401) {
        setzeToken("");
        reject(new ApiFehler(401, "Anmeldung erforderlich"));
        return;
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText) as Knoten);
        } catch {
          reject(new ApiFehler(xhr.status, "Ungueltige Antwort"));
        }
      } else {
        let text = xhr.statusText;
        try {
          text = JSON.parse(xhr.responseText).detail ?? text;
        } catch {
          // Text bleibt
        }
        reject(new ApiFehler(xhr.status, text));
      }
    };
    xhr.onerror = () => reject(new ApiFehler(0, "Netzwerkfehler"));
    xhr.onabort = () => reject(new ApiFehler(0, "Abgebrochen"));
    griffSetzen?.({ abbrechen: () => xhr.abort() });
    const formular = new FormData();
    formular.append("datei", datei);
    if (parentId) formular.append("parent_id", parentId);
    xhr.send(formular);
  });
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

export async function zipHerunterladen(ids: string[], dateiname: string): Promise<void> {
  const antwort = await fetch("/api/v1/dateien/zip", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Kellerwolke-Sitzung": token() },
    body: JSON.stringify({ ids }),
  });
  await pruefe(antwort);
  const blob = await antwort.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = dateiname;
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

export function endgueltigLoeschen(id: string): Promise<void> {
  return hole<void>(`/v1/dateien/${id}/endgueltig`, { method: "DELETE" });
}

export function versionen(id: string): Promise<Version[]> {
  return hole<Version[]>(`/v1/dateien/${id}/versionen`);
}

// --- Suche ------------------------------------------------------------------

export function suchen(q: string): Promise<Knoten[]> {
  return hole<Knoten[]>(`/v1/suche?q=${encodeURIComponent(q)}`);
}

// --- Externe Quellen --------------------------------------------------------

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

export function externOrdnerAnlegen(
  knotenId: string,
  unterpfad: string,
  name: string,
): Promise<void> {
  return hole<void>(`/v1/dateien/extern/${knotenId}/ordner`, {
    method: "POST",
    body: JSON.stringify({ name, unterpfad }),
  });
}

export async function externHochladen(
  knotenId: string,
  unterpfad: string,
  datei: File,
): Promise<void> {
  const formular = new FormData();
  formular.append("datei", datei);
  formular.append("unterpfad", unterpfad);
  const antwort = await fetch(`/api/v1/dateien/extern/${knotenId}/upload`, {
    method: "POST",
    headers: { "X-Kellerwolke-Sitzung": token() },
    body: formular,
  });
  await pruefe(antwort);
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

export function datenablageVerschieben(ziel: string): Promise<Verschiebung> {
  return hole<Verschiebung>("/v1/admin/speicherort/verschieben", {
    method: "POST",
    body: JSON.stringify({ ziel }),
  });
}

export function verschiebungStand(): Promise<Verschiebung> {
  return hole<Verschiebung>("/v1/admin/speicherort/verschieben");
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

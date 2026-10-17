import type {
  AppZugang,
  AppZugangNeu,
  AuthStatus,
  Benutzer,
  ExternEintrag,
  Freigabe,
  GeraeteArt,
  Geraet,
  Knoten,
  Konto,
  Kopplung,
  Medium,
  Pfadteil,
  PoolAufraeumen,
  PoolPruefung,
  Recht,
  SpeicherStatus,
  Verschiebung,
  Version,
  Vorgang,
} from "./types";
import { verbindung } from "./verbindung.svelte";

// Sitzungs-Token im localStorage und im Header (kein Cookie). Bewusste Wahl für
// eine lokale Familien-Cloud: einfache, CSRF-unempfindliche Header-Authentifizierung.
// Das Frontend nutzt nirgends @html, die XSS-Fläche ist entsprechend klein.
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

// Wer reagiert, wenn der Server die Sitzung nicht mehr kennt (abgelaufen, gesperrt, anderswo abgemeldet):
// die Anmeldung meldet sich hier an und zeigt dann wieder den Anmeldeschirm.
let beiSitzungsende: (() => void) | null = null;
export function sitzungsendeMelden(fn: () => void): void {
  beiSitzungsende = fn;
}
function sitzungVorbei(): ApiFehler {
  setzeToken("");
  beiSitzungsende?.();
  return new ApiFehler(401, "Anmeldung erforderlich");
}

async function pruefe(antwort: Response): Promise<Response> {
  if (antwort.status === 401) throw sitzungVorbei();
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
  let antwort: Response;
  try {
    antwort = await fetch(`/api${pfad}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        "X-Kellerwolke-Sitzung": token(),
        ...(init.headers ?? {}),
      },
    });
  } catch {
    verbindung.ok = false;
    throw new ApiFehler(0, "Keine Verbindung zur Kellerwolke");
  }
  verbindung.ok = true;
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

// Änderungs-Journal des Nutzers ab einer Sequenznummer (für Live-Abgleich).
export function journalSeit(seit: number): Promise<{ seq: number }[]> {
  return hole<{ seq: number }[]>(`/v1/sync/journal?seit=${seit}`);
}

// Letzte vergebene Journal-Nummer: Startpunkt des Live-Abgleichs (nichts nachladen, nichts verpassen).
export async function journalStand(): Promise<number> {
  return (await hole<{ seq: number }>("/v1/sync/stand")).seq;
}

// --- Lesezugang für Inhaltsadressen (Vorschau, Wiedergabe, Herunterladen) ---------------------------
// <img>, <audio>, <video> und Download-Links können keinen Kopf setzen. Der Server legt dafür ein
// Cookie nur für /api/v1/inhalt an (für Skripte unlesbar, an die Sitzung gebunden).

export function lesezugangEinrichten(): Promise<void> {
  return hole<void>("/v1/inhalt/zugang", { method: "POST" });
}

export async function lesezugangBeenden(): Promise<void> {
  try {
    await fetch("/api/v1/inhalt/zugang", { method: "DELETE" });
  } catch {
    // egal - mit der Sitzung endet er ohnehin
  }
}

// Lädt über einen unsichtbaren Link: der Browser holt direkt aus dem Strom, mit Fortschritt und ohne
// die Datei im Speicher der Seite zu halten.
function ueberLink(url: string, name: string): void {
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  a.remove();
}

export function herunterladen(knoten: Knoten): void {
  ueberLink(`/api/v1/inhalt/datei/${knoten.id}`, knoten.name);
}

export function externHerunterladen(knotenId: string, unterpfad: string, name: string): void {
  ueberLink(`/api/v1/inhalt/extern/${knotenId}?unterpfad=${encodeURIComponent(unterpfad)}`, name);
}

// ZIP: erst die Auswahl prüfen (Fehler wie "zu gross" kommen so als Meldung), dann als Formular in einen
// unsichtbaren Rahmen abschicken - eine lange Auswahl passt in keine Adresse.
export async function zipHerunterladen(ids: string[], dateiname: string): Promise<void> {
  await hole<{ eintraege: number }>("/v1/dateien/zip/plan", { method: "POST", body: JSON.stringify({ ids }) });
  let rahmen = document.querySelector<HTMLIFrameElement>("iframe[name=kw-download]");
  if (!rahmen) {
    rahmen = document.createElement("iframe");
    rahmen.name = "kw-download";
    rahmen.hidden = true;
    document.body.appendChild(rahmen);
  }
  const formular = document.createElement("form");
  formular.method = "POST";
  formular.action = "/api/v1/inhalt/zip";
  formular.target = "kw-download";
  formular.hidden = true;
  for (const [schluessel, wert] of [...ids.map((id) => ["ids", id]), ["name", dateiname]]) {
    const feld = document.createElement("input");
    feld.type = "hidden";
    feld.name = schluessel;
    feld.value = wert;
    formular.appendChild(feld);
  }
  document.body.appendChild(formular);
  formular.submit();
  formular.remove();
}

export function pfadVon(id: string): Promise<Pfadteil[]> {
  return hole<Pfadteil[]>(`/v1/dateien/${id}/pfad`);
}

export function alleMedien(): Promise<Medium[]> {
  return hole<Medium[]>("/v1/medien/alle");
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

// Upload über XMLHttpRequest, damit der echte Sende-Fortschritt verfolgt und
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
        reject(sitzungVorbei());
        return;
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText) as Knoten);
        } catch {
          reject(new ApiFehler(xhr.status, "Ungültige Antwort"));
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
    xhr.onerror = () => {
      verbindung.ok = false;
      reject(new ApiFehler(0, "Keine Verbindung zur Kellerwolke"));
    };
    xhr.onabort = () => reject(new ApiFehler(0, "Abgebrochen"));
    griffSetzen?.({ abbrechen: () => xhr.abort() });
    const formular = new FormData();
    formular.append("datei", datei);
    if (parentId) formular.append("parent_id", parentId);
    xhr.send(formular);
  });
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

export function poolPruefung(tief = false): Promise<PoolPruefung> {
  return hole<PoolPruefung>(`/v1/admin/pool-pruefung?tief=${tief ? "true" : "false"}`);
}

export function poolAufraeumen(): Promise<PoolAufraeumen> {
  return hole<PoolAufraeumen>("/v1/admin/pool-aufraeumen", { method: "POST" });
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

// --- Zugänge für eigene Apps (Schlüssel mit Rechten je Ordner) -------------------
export function zugaenge(): Promise<AppZugang[]> {
  return hole<AppZugang[]>("/v1/app-zugaenge");
}

export function zugangAnlegen(app: string): Promise<AppZugangNeu> {
  return hole<AppZugangNeu>("/v1/app-zugaenge", { method: "POST", body: JSON.stringify({ app }) });
}

export function zugangErneuern(id: string): Promise<AppZugangNeu> {
  return hole<AppZugangNeu>(`/v1/app-zugaenge/${id}/erneuern`, { method: "POST" });
}

export function zugangAktiv(id: string, aktiv: boolean): Promise<AppZugang> {
  return hole<AppZugang>(`/v1/app-zugaenge/${id}`, { method: "PATCH", body: JSON.stringify({ aktiv }) });
}

export function zugangRechte(id: string, rechte: { knoten_id: string; recht: Recht }[]): Promise<AppZugang> {
  return hole<AppZugang>(`/v1/app-zugaenge/${id}/rechte`, { method: "PUT", body: JSON.stringify({ rechte }) });
}

export function zugangLoeschen(id: string): Promise<void> {
  return hole<void>(`/v1/app-zugaenge/${id}`, { method: "DELETE" });
}

// --- Gekoppelte Geräte ------------------------------------------------------
// Das Gerät löst den Code ohne Anmeldung ein; sein Schlüssel geht danach wie ein Sitzungs-Token mit.
export async function koppeln(code: string, name: string, art: GeraeteArt): Promise<Benutzer> {
  const daten = await hole<{ schluessel: string; benutzer: Benutzer }>("/v1/geraete/koppeln", {
    method: "POST",
    body: JSON.stringify({ code, name, art }),
  });
  setzeToken(daten.schluessel);
  return daten.benutzer;
}

export function geraete(): Promise<Geraet[]> {
  return hole<Geraet[]>("/v1/geraete");
}

// Das Gerät, das gerade fragt; 404, wenn mit Passwort angemeldet.
export function diesesGeraet(): Promise<Geraet> {
  return hole<Geraet>("/v1/geraete/dieses");
}

export function kopplungStarten(): Promise<Kopplung> {
  return hole<Kopplung>("/v1/geraete/kopplung", { method: "POST" });
}

export function kopplungStand(id: string): Promise<Kopplung> {
  return hole<Kopplung>(`/v1/geraete/kopplung/${id}`);
}

export function kopplungAbbrechen(id: string): Promise<void> {
  return hole<void>(`/v1/geraete/kopplung/${id}`, { method: "DELETE" });
}

export function geraetUmbenennen(id: string, name: string): Promise<Geraet> {
  return hole<Geraet>(`/v1/geraete/${id}`, { method: "PATCH", body: JSON.stringify({ name }) });
}

export function geraetTrennen(id: string): Promise<void> {
  return hole<void>(`/v1/geraete/${id}`, { method: "DELETE" });
}

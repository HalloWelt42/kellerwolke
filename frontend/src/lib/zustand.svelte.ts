import * as api from "./api";
import { Browser, erzeugeBrowser } from "./browser.svelte";
import type { Knoten, SpeicherStatus, Vorgang } from "./types";

// App-globaler Zustand: alles, was NICHT zu einer einzelnen Browsing-Flaeche
// gehoert (Hintergrund-Vorgaenge, Upload-Fortschrittskarte, Speicheranzeige,
// Version, ein-/ausgeklappte Navigation, Einzel-/Split-Modus). Die eigentliche
// Dateiansicht steckt in Browser-Instanzen: `haupt` ist die Einzelansicht, der
// Splitscreen erzeugt weitere. So gibt es nur EINE Browsing-Implementierung,
// von Einzel- und Split-Ansicht geteilt.

export type { Bereich, Ansicht, Pfadteil } from "./browser.svelte";

export interface UploadFortschritt {
  name: string;
  prozent: number;
  geladen: number;
  gesamt: number;
  tempo: number; // Bytes pro Sekunde
  restzeit: number; // Sekunden, -1 = unbekannt
}

// Die Einzelansicht. Navigation, Werkzeugleiste, Detail-Pane und der globale
// Live-Abgleich beziehen sich auf diese Instanz.
export const haupt: Browser = erzeugeBrowser();

export const zustand = $state<{
  split: boolean; // Einzel- vs. Splitscreen-Modus
  navAus: boolean;
  uploads: UploadFortschritt[];
  speicher: SpeicherStatus | null;
  version: string;
  vorgaenge: Vorgang[];
  vorgaengeOffen: boolean;
}>({
  split: false,
  navAus: false,
  uploads: [],
  speicher: null,
  version: "",
  vorgaenge: [],
  vorgaengeOffen: false,
});

// --- Modus-Umschalter --------------------------------------------------------

export function navUmschalten(): void {
  zustand.navAus = !zustand.navAus;
}

export function splitUmschalten(): void {
  zustand.split = !zustand.split;
}

// --- Hintergrund-Vorgaenge ---------------------------------------------------

export async function ladeVorgaenge(): Promise<void> {
  try {
    zustand.vorgaenge = await api.vorgaenge();
  } catch {
    // Vorgaenge sind Nebeninfo; Fehler hier nicht aufdraengen.
  }
}

export function vorgaengeUmschalten(): void {
  zustand.vorgaengeOffen = !zustand.vorgaengeOffen;
  if (zustand.vorgaengeOffen) ladeVorgaenge();
}

export async function vorgangAbbrechen(id: string): Promise<void> {
  try {
    await api.vorgangAbbrechen(id);
    await ladeVorgaenge();
  } catch (f) {
    haupt.fehler = (f as Error).message;
  }
}

export async function vorgaengeAufraeumen(): Promise<void> {
  try {
    await api.vorgaengeAufraeumen();
    await ladeVorgaenge();
  } catch (f) {
    haupt.fehler = (f as Error).message;
  }
}

// --- Live-Abgleich ueber das Aenderungs-Journal -----------------------------
// Pollt das Journal des Nutzers; sobald neue Eintraege auftauchen (eigene
// andere Sitzung, WebDAV, kuenftig Freigaben), wird die Hauptansicht
// aktualisiert - ohne Reload.
let letzteSeq = 0;
let liveInit = false;
let liveTimer: ReturnType<typeof setInterval> | null = null;
let speicherTick = 0;

async function pollJournal(): Promise<void> {
  try {
    const neue = await api.journalSeit(letzteSeq);
    if (neue.length === 0) return;
    letzteSeq = neue.reduce((m, e) => Math.max(m, e.seq), letzteSeq);
    if (!liveInit) {
      liveInit = true; // erster Lauf setzt nur den Stand
      return;
    }
    haupt.aktualisiere();
    ladeSpeicher();
  } catch {
    // Live-Abgleich ist optional; bei Fehlern still weiter.
  }
}

async function liveTick(): Promise<void> {
  await pollJournal();
  // Vorgaenge nur abfragen, wenn die Schublade offen ist oder noch etwas
  // laeuft - sonst spart man die Anfrage.
  if (zustand.vorgaengeOffen || zustand.vorgaenge.some((v) => v.status === "laeuft")) {
    await ladeVorgaenge();
  }
  // Speicher-Verfuegbarkeit ueberwachen: ist der Pool gerade abgehaengt, jeden
  // Tick neu fragen (Banner verschwindet sofort beim Remount), sonst nur alle
  // ~20 s als Herzschlag.
  speicherTick += 1;
  if (zustand.speicher?.verfuegbar === false || speicherTick % 5 === 0) {
    await ladeSpeicher();
  }
}

export function starteLiveAbgleich(): void {
  if (liveTimer) return;
  liveInit = false;
  letzteSeq = 0;
  ladeSpeicher();
  liveTick();
  liveTimer = setInterval(liveTick, 4000);
}

export function stoppeLiveAbgleich(): void {
  if (liveTimer) {
    clearInterval(liveTimer);
    liveTimer = null;
  }
}

export async function ladeVersion(): Promise<void> {
  try {
    zustand.version = await api.version();
  } catch {
    // Versionsanzeige ist optional.
  }
}

export async function ladeSpeicher(): Promise<void> {
  try {
    zustand.speicher = await api.speicherStatus();
  } catch {
    // Speicheranzeige ist optional.
  }
}

export async function leerePapierkorb(): Promise<void> {
  try {
    await api.papierkorbLeeren();
    haupt.auswahl.leeren();
    await haupt.ladeMit(() => api.papierkorb());
    ladeSpeicher();
  } catch (f) {
    haupt.fehler = (f as Error).message;
  }
}

// --- Upload mit Fortschrittskarte (app-global) ------------------------------
// Der Upload schreibt in die globale Fortschrittskarte (eine zur Zeit), legt
// die Dateien aber im Ordner des uebergebenen Browsers ab (Einzelansicht oder
// eine bestimmte Pane).

let aktuellerUploadGriff: (() => void) | null = null;
let uploadAbgebrochen = false;

export function uploadStoppen(): void {
  uploadAbgebrochen = true;
  aktuellerUploadGriff?.();
}

async function externHochladen(ziel: Browser, dateien: File[]): Promise<void> {
  const b = ziel.externBrowse;
  if (!b) return;
  ziel.fehler = "";
  try {
    for (const d of dateien) {
      await api.externHochladen(b.knotenId, b.unterpfad.join("/"), d);
    }
    await ziel.ladeExtern();
  } catch (f) {
    ziel.fehler = (f as Error).message;
  }
}

export async function hochladen(
  dateien: FileList | File[] | null,
  ziel: Browser = haupt,
): Promise<void> {
  if (!dateien) return;
  const liste = Array.from(dateien);
  if (liste.length === 0) return;
  // In einer externen Quelle direkt dorthin schreiben (ohne die Fortschritts-
  // Karte des eigenen Speichers).
  if (ziel.bereich === "extern" && ziel.externBrowse) {
    return externHochladen(ziel, liste);
  }
  // Kein zweiter, ueberlappender Upload: der wuerde Fortschrittskarte und
  // Abbruch-Griff des laufenden ueberschreiben.
  if (zustand.uploads.length > 0) return;
  const ordner = ziel.aktuellerOrdner;
  ziel.fehler = "";
  uploadAbgebrochen = false;
  zustand.uploads = liste.map((d) => ({
    name: d.name,
    prozent: 0,
    geladen: 0,
    gesamt: d.size,
    tempo: 0,
    restzeit: -1,
  }));
  try {
    for (let i = 0; i < liste.length; i++) {
      if (uploadAbgebrochen) break;
      let letzteZeit = Date.now();
      let letzteBytes = 0;
      try {
        await api.hochladen(
          liste[i],
          ordner,
          (geladen, gesamt) => {
            const u = zustand.uploads[i];
            if (!u) return;
            const jetzt = Date.now();
            const dt = (jetzt - letzteZeit) / 1000;
            if (dt >= 0.2) {
              u.tempo = (geladen - letzteBytes) / dt;
              letzteBytes = geladen;
              letzteZeit = jetzt;
            }
            u.geladen = geladen;
            u.gesamt = gesamt;
            u.prozent = gesamt ? Math.round((geladen / gesamt) * 100) : 0;
            u.restzeit = u.tempo > 0 ? (gesamt - geladen) / u.tempo : -1;
          },
          (griff) => {
            aktuellerUploadGriff = griff.abbrechen;
          },
        );
        const u = zustand.uploads[i];
        if (u) {
          u.prozent = 100;
          u.restzeit = 0;
        }
      } catch (f) {
        if (uploadAbgebrochen) break;
        ziel.fehler = (f as Error).message;
        break;
      }
    }
  } finally {
    aktuellerUploadGriff = null;
    zustand.uploads = [];
    await ziel.ladeOrdner();
    ladeSpeicher();
    // Jeder Upload startet einen Indizierungs-Vorgang - sofort anzeigen.
    ladeVorgaenge();
  }
}

// --- Ordner-Upload (Drag-and-drop ganzer Ordner) ---------------------------
// Traversiert die abgelegten Eintraege, legt die Ordnerstruktur an und laedt
// alle Dateien an ihren Platz. Die Eintraege werden in aufDrop synchron per
// webkitGetAsEntry eingesammelt und hier asynchron abgearbeitet.

async function sammleDateien(
  eintrag: FileSystemEntry,
  pfad: string[],
  raus: { datei: File; pfad: string[] }[],
): Promise<void> {
  if (eintrag.isFile) {
    const datei = await new Promise<File>((res, rej) => (eintrag as FileSystemFileEntry).file(res, rej));
    raus.push({ datei, pfad });
  } else if (eintrag.isDirectory) {
    const leser = (eintrag as FileSystemDirectoryEntry).createReader();
    // readEntries liefert hoechstens ~100 Eintraege je Aufruf - bis leer wiederholen.
    let stapel: FileSystemEntry[];
    do {
      stapel = await new Promise<FileSystemEntry[]>((res, rej) => leser.readEntries(res, rej));
      for (const k of stapel) await sammleDateien(k, [...pfad, eintrag.name], raus);
    } while (stapel.length > 0);
  }
}

// Legt einen Ordner an oder liefert den vorhandenen gleichen Namens (die
// Datenbank verbietet doppelte Namen je Elternordner) - wiederholte Ablagen
// mischen sich so in den vorhandenen Baum, statt zu scheitern.
async function ordnerSicherstellen(name: string, parentId: string | null): Promise<string> {
  try {
    return (await api.ordnerAnlegen(name, parentId)).id;
  } catch (e) {
    let kinder: Knoten[] = [];
    try {
      kinder = await api.kinder(parentId);
    } catch {
      // Auflisten fehlgeschlagen - unten den Originalfehler werfen.
    }
    const vorhanden = kinder.find((k) => k.typ === "ordner" && k.name.toLowerCase() === name.toLowerCase());
    if (vorhanden) return vorhanden.id;
    throw e;
  }
}

export async function strukturHochladen(eintraege: FileSystemEntry[], ziel: Browser = haupt): Promise<void> {
  if (zustand.uploads.length > 0) return; // kein ueberlappender Upload
  const alle: { datei: File; pfad: string[] }[] = [];
  for (const e of eintraege) await sammleDateien(e, [], alle);
  if (alle.length === 0) return;

  const start = ziel.aktuellerOrdner;
  ziel.fehler = "";
  uploadAbgebrochen = false;

  // Ordnerstruktur anlegen (kuerzeste Pfade zuerst), Pfad -> Ordner-Id.
  const idFuer = new Map<string, string | null>();
  idFuer.set("", start);
  const pfade = new Set<string>();
  for (const { pfad } of alle) for (let i = 1; i <= pfad.length; i++) pfade.add(pfad.slice(0, i).join("/"));
  const sortiert = [...pfade].sort((a, b) => a.split("/").length - b.split("/").length);
  try {
    for (const p of sortiert) {
      const teile = p.split("/");
      const eltern = idFuer.get(teile.slice(0, -1).join("/")) ?? start;
      idFuer.set(p, await ordnerSicherstellen(teile[teile.length - 1], eltern));
    }
  } catch (e) {
    ziel.fehler = "Ordner konnte nicht angelegt werden: " + (e as Error).message;
    return;
  }

  // Dateien hochladen (Fortschrittskarte je Datei, mit Ordner als Ziel).
  zustand.uploads = alle.map(({ datei }) => ({ name: datei.name, prozent: 0, geladen: 0, gesamt: datei.size, tempo: 0, restzeit: -1 }));
  try {
    for (let i = 0; i < alle.length; i++) {
      if (uploadAbgebrochen) break;
      const { datei, pfad } = alle[i];
      const parentId = idFuer.get(pfad.join("/")) ?? start;
      let letzteZeit = Date.now();
      let letzteBytes = 0;
      try {
        await api.hochladen(
          datei,
          parentId,
          (geladen, gesamt) => {
            const u = zustand.uploads[i];
            if (!u) return;
            const jetzt = Date.now();
            const dt = (jetzt - letzteZeit) / 1000;
            if (dt >= 0.2) {
              u.tempo = (geladen - letzteBytes) / dt;
              letzteBytes = geladen;
              letzteZeit = jetzt;
            }
            u.geladen = geladen;
            u.gesamt = gesamt;
            u.prozent = gesamt ? Math.round((geladen / gesamt) * 100) : 0;
            u.restzeit = u.tempo > 0 ? (gesamt - geladen) / u.tempo : -1;
          },
          (griff) => {
            aktuellerUploadGriff = griff.abbrechen;
          },
        );
        const u = zustand.uploads[i];
        if (u) {
          u.prozent = 100;
          u.restzeit = 0;
        }
      } catch (f) {
        if (uploadAbgebrochen) break;
        ziel.fehler = (f as Error).message;
        break;
      }
    }
  } finally {
    aktuellerUploadGriff = null;
    zustand.uploads = [];
    await ziel.ladeOrdner();
    ladeSpeicher();
    ladeVorgaenge();
  }
}

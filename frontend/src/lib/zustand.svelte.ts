import * as api from "./api";
import { Browser, erzeugeBrowser } from "./browser.svelte";
import { eindeutigeId } from "./id";
import type { Knoten, SpeicherStatus, Vorgang } from "./types";

// App-globaler Zustand: alles, was NICHT zu einer einzelnen Browsing-Fläche
// gehört (Hintergrund-Vorgänge, Upload-Warteschlange, Speicheranzeige,
// Version, Navigation, Einzel-/Split-Modus). Die Dateiansicht steckt in
// Browser-Instanzen: `haupt` ist die Einzelansicht, der Splitscreen meldet
// seine Panes als weitere Flächen an.

export type { Bereich, Ansicht, Pfadteil } from "./browser.svelte";

export type UploadStatus = "wartet" | "laeuft" | "fertig" | "fehler";

export interface UploadFortschritt {
  id: string;
  name: string;
  status: UploadStatus;
  prozent: number;
  geladen: number;
  gesamt: number;
  tempo: number; // Bytes pro Sekunde
  restzeit: number; // Sekunden, -1 = unbekannt
  fehler: string;
}

// Die Einzelansicht. Navigation, Werkzeugleiste und Detail-Pane beziehen sich
// auf diese Instanz.
export const haupt: Browser = erzeugeBrowser();

// Die Panes des Splitscreens leben länger als das Bauteil: wer kurz in die
// Einzelansicht oder zu den Medien wechselt, findet sie am selben Ort wieder.
export const panes: Browser[] = [erzeugeBrowser(), erzeugeBrowser()];

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

// --- Flächen ----------------------------------------------------------------
// Jede sichtbare Fläche (haupt oder eine Pane) hängt am Live-Abgleich; die
// aktive ist die, auf die sich Ablegen und "Zum Ordner" beziehen.

const flaechen = new Set<Browser>([haupt]);
const flaechenZustand = $state<{ aktiv: Browser }>({ aktiv: haupt });

export function flaecheAnmelden(b: Browser): void {
  flaechen.add(b);
}

export function flaecheAbmelden(b: Browser): void {
  if (b === haupt) return;
  flaechen.delete(b);
  if (flaechenZustand.aktiv === b) flaechenZustand.aktiv = haupt;
}

export function flaecheAktivieren(b: Browser): void {
  flaechenZustand.aktiv = b;
}

export function aktiveFlaeche(): Browser {
  return zustand.split ? flaechenZustand.aktiv : haupt;
}

function alleAktualisieren(): void {
  for (const b of flaechen) b.aktualisiere();
}

// Weitere Ansichten, die bei Änderungen nachziehen (etwa "Alle Medien").
const beobachter = new Set<() => void>();
export function beiAenderung(fn: () => void): () => void {
  beobachter.add(fn);
  return () => beobachter.delete(fn);
}

// Konto verlassen (Abmelden, Sitzung abgelaufen): keine Fläche zeigt danach
// noch etwas vom bisherigen Konto, laufende Uploads enden.
export function kontoVerlassen(): void {
  uploadStoppen();
  stoppeLiveAbgleich();
  for (const b of [haupt, ...panes]) b.zuruecksetzen();
  flaechenZustand.aktiv = haupt;
  zustand.split = false;
  zustand.vorgaenge = [];
  zustand.vorgaengeOffen = false;
  zustand.speicher = null;
}

// --- Modus-Umschalter --------------------------------------------------------

export function navUmschalten(): void {
  zustand.navAus = !zustand.navAus;
}

export function splitUmschalten(): void {
  zustand.split = !zustand.split;
}

// --- Hintergrund-Vorgänge ---------------------------------------------------

export async function ladeVorgaenge(): Promise<void> {
  try {
    zustand.vorgaenge = await api.vorgaenge();
  } catch {
    // Vorgänge sind Nebeninfo; Fehler hier nicht aufdrängen.
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

// --- Live-Abgleich über das Änderungs-Journal -----------------------------
// Startpunkt ist der aktuelle Stand des Journals: nichts wird nachgeladen,
// keine spätere Änderung geht verloren. Neue Einträge (andere Sitzung,
// WebDAV, Apps, eigene Aktionen) aktualisieren alle Flächen still.
let letzteSeq: number | null = null;
let liveTimer: ReturnType<typeof setInterval> | null = null;
let speicherTick = 0;

async function pollJournal(): Promise<void> {
  try {
    if (letzteSeq === null) {
      letzteSeq = await api.journalStand();
      return;
    }
    const neue = await api.journalSeit(letzteSeq);
    if (neue.length === 0) return;
    letzteSeq = neue.reduce((m, e) => Math.max(m, e.seq), letzteSeq);
    alleAktualisieren();
    for (const fn of beobachter) fn();
    ladeSpeicher();
  } catch {
    // Live-Abgleich ist optional; bei Fehlern still weiter.
  }
}

async function liveTick(): Promise<void> {
  await pollJournal();
  // Vorgänge nur abfragen, wenn die Schublade offen ist oder noch etwas läuft.
  if (zustand.vorgaengeOffen || zustand.vorgaenge.some((v) => v.status === "laeuft")) {
    await ladeVorgaenge();
  }
  // Speicher-Verfügbarkeit: abgehängt jeden Tick neu fragen, sonst alle ~20 s.
  speicherTick += 1;
  if (zustand.speicher?.verfuegbar === false || speicherTick % 5 === 0) {
    await ladeSpeicher();
  }
}

export function starteLiveAbgleich(): void {
  if (liveTimer) return;
  letzteSeq = null;
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
  } catch (f) {
    haupt.fehler = (f as Error).message;
  }
  haupt.auswahl.leeren();
  await haupt.aktualisiere();
  ladeSpeicher();
}

export async function endgueltigLoeschen(ziel: Browser, ids: string[]): Promise<void> {
  await ziel.endgueltigLoeschen(ids);
  ladeSpeicher();
}

// --- Upload-Warteschlange (app-global) ----------------------------------------
// Jede Ablage hängt ihre Dateien an; eine Datei nach der anderen geht hinaus.
// Scheitert eine, laufen die übrigen weiter; am Ende steht in der Fläche,
// welche nicht ankamen und warum.

// Systemdateien, die niemand in der Wolke haben will.
function istSystemdatei(name: string): boolean {
  return name === ".DS_Store" || name === "Thumbs.db" || name === "desktop.ini" || name.startsWith("._");
}

interface Auftrag {
  datei: File;
  parentId: string | null;
  ziel: Browser;
  eintrag: UploadFortschritt;
}

let warteschlange: Auftrag[] = [];
let laeuft = false;
let aktuellerUploadGriff: (() => void) | null = null;
let abgebrochen = false;

export function uploadStoppen(): void {
  abgebrochen = true;
  aktuellerUploadGriff?.();
}

function einreihen(dateien: File[], parentId: (d: File, i: number) => string | null, ziel: Browser): void {
  for (const [i, datei] of dateien.entries()) {
    if (istSystemdatei(datei.name)) continue;
    const eintrag: UploadFortschritt = {
      id: eindeutigeId(), name: datei.name, status: "wartet", prozent: 0, geladen: 0, gesamt: datei.size,
      tempo: 0, restzeit: -1, fehler: "",
    };
    zustand.uploads.push(eintrag);
    warteschlange.push({ datei, parentId: parentId(datei, i), ziel, eintrag: zustand.uploads[zustand.uploads.length - 1] });
  }
  if (!laeuft) abarbeiten();
}

async function einenHochladen(a: Auftrag): Promise<void> {
  const u = a.eintrag;
  u.status = "laeuft";
  let letzteZeit = Date.now();
  let letzteBytes = 0;
  await api.hochladen(
    a.datei,
    a.parentId,
    (geladen, gesamt) => {
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
  u.status = "fertig";
  u.prozent = 100;
  u.restzeit = 0;
}

async function abarbeiten(): Promise<void> {
  laeuft = true;
  abgebrochen = false;
  const betroffen = new Set<Browser>();
  const fehlschlaege = new Map<Browser, string[]>();
  try {
    while (warteschlange.length && !abgebrochen) {
      const a = warteschlange.shift() as Auftrag;
      betroffen.add(a.ziel);
      try {
        await einenHochladen(a);
      } catch (f) {
        if (abgebrochen) break;
        a.eintrag.status = "fehler";
        a.eintrag.fehler = (f as Error).message;
        fehlschlaege.set(a.ziel, [...(fehlschlaege.get(a.ziel) ?? []), `${a.datei.name} (${a.eintrag.fehler})`]);
      }
      aktuellerUploadGriff = null;
    }
  } finally {
    warteschlange = [];
    laeuft = false;
    zustand.uploads = [];
    for (const [ziel, liste] of fehlschlaege) {
      ziel.fehler = `${liste.length === 1 ? "1 Datei" : `${liste.length} Dateien`} nicht hochgeladen: ${liste.join(", ")}`;
    }
    alleAktualisieren();
    ladeSpeicher();
    ladeVorgaenge(); // jeder Upload startet einen Indizierungs-Vorgang
  }
}

export function hochladen(dateien: FileList | File[] | null, ziel: Browser = haupt): void {
  if (!dateien || !ziel.rechte.anlegen) return;
  const ordner = ziel.aktuellerOrdner;
  einreihen(Array.from(dateien), () => ordner, ziel);
}

// --- Ordner-Upload (ganze Ordner abgelegt) -------------------------------------
// Traversiert die abgelegten Einträge, legt die Ordnerstruktur an und reiht
// alle Dateien an ihren Platz ein.

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
    // readEntries liefert höchstens ~100 Einträge je Aufruf - bis leer wiederholen.
    let stapel: FileSystemEntry[];
    do {
      stapel = await new Promise<FileSystemEntry[]>((res, rej) => leser.readEntries(res, rej));
      for (const k of stapel) await sammleDateien(k, [...pfad, eintrag.name], raus);
    } while (stapel.length > 0);
  }
}

// Legt einen Ordner an oder liefert den vorhandenen gleichen Namens - wiederholte
// Ablagen mischen sich so in den vorhandenen Baum, statt zu scheitern.
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
  if (!ziel.rechte.anlegen) return;
  const start = ziel.aktuellerOrdner;
  const alle: { datei: File; pfad: string[] }[] = [];
  try {
    for (const e of eintraege) await sammleDateien(e, [], alle);
  } catch (f) {
    ziel.fehler = "Ordner konnte nicht gelesen werden: " + (f as Error).message;
    return;
  }
  const dateien = alle.filter(({ datei }) => !istSystemdatei(datei.name));
  // Ordnerstruktur anlegen (kürzeste Pfade zuerst), Pfad -> Ordner-Id.
  const idFuer = new Map<string, string | null>([["", start]]);
  const pfade = new Set<string>();
  for (const e of eintraege) if (e.isDirectory) pfade.add(e.name); // auch leere Ordner
  for (const { pfad } of dateien) for (let i = 1; i <= pfad.length; i++) pfade.add(pfad.slice(0, i).join("/"));
  const sortiert = [...pfade].sort((a, b) => a.split("/").length - b.split("/").length);
  try {
    for (const p of sortiert) {
      const teile = p.split("/");
      const eltern = idFuer.get(teile.slice(0, -1).join("/")) ?? start;
      idFuer.set(p, await ordnerSicherstellen(teile[teile.length - 1], eltern));
    }
  } catch (f) {
    ziel.fehler = "Ordner konnte nicht angelegt werden: " + (f as Error).message;
    await ziel.aktualisiere();
    return;
  }
  if (dateien.length === 0) {
    await ziel.aktualisiere();
    return;
  }
  einreihen(dateien.map((d) => d.datei), (_d, i) => idFuer.get(dateien[i].pfad.join("/")) ?? start, ziel);
}

// --- Ablegen aus dem Dateisystem ------------------------------------------------
// Ein Weg für jede Ablagefläche (Fenster, Liste, Pane). dataTransfer gilt nur
// während des Ereignisses: Einträge werden synchron eingesammelt.

export function hatDateien(e: DragEvent): boolean {
  return Array.from(e.dataTransfer?.types ?? []).includes("Files");
}

export function ablegen(e: DragEvent, ziel: Browser): boolean {
  if (!ziel.rechte.anlegen) return false;
  const posten = e.dataTransfer?.items;
  if (posten && posten.length && typeof posten[0].webkitGetAsEntry === "function") {
    const eintraege: FileSystemEntry[] = [];
    for (const p of Array.from(posten)) {
      const en = p.webkitGetAsEntry?.();
      if (en) eintraege.push(en);
    }
    if (eintraege.some((en) => en.isDirectory)) {
      strukturHochladen(eintraege, ziel);
      return true;
    }
  }
  hochladen(e.dataTransfer?.files ?? null, ziel);
  return true;
}

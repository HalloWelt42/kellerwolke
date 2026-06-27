import * as api from "./api";
import { auswahl } from "./auswahl.svelte";
import type { ExternEintrag, Knoten, SpeicherStatus, Version } from "./types";

// Zentraler Zustand des Dateibrowsers: Single Source of Truth fuer Navigation,
// Liste, Detail-Pane und Auswahl. Die Zonen (Navigation, Inhalt, Detail) lesen
// hier und rufen die Aktionen auf. Backend-Funktionen kommen unveraendert aus
// api.ts.

export type Bereich = "dateien" | "extern" | "papierkorb" | "suche";
export type Ansicht = "liste" | "grid";

export interface Pfadteil {
  id: string | null;
  name: string;
}

export interface UploadFortschritt {
  name: string;
  prozent: number;
  geladen: number;
  gesamt: number;
  tempo: number; // Bytes pro Sekunde
  restzeit: number; // Sekunden, -1 = unbekannt
}

export const zustand = $state<{
  bereich: Bereich;
  pfad: Pfadteil[];
  eintraege: Knoten[];
  ansicht: Ansicht;
  laden: boolean;
  fehler: string;
  suchbegriff: string;
  detail: Knoten | null;
  detailVersionen: Version[];
  externBrowse: { knotenId: string; name: string; unterpfad: string[] } | null;
  externEintraege: ExternEintrag[];
  uploads: UploadFortschritt[];
  speicher: SpeicherStatus | null;
  version: string;
}>({
  bereich: "dateien",
  pfad: [{ id: null, name: "Meine Dateien" }],
  eintraege: [],
  ansicht: "liste",
  laden: false,
  fehler: "",
  suchbegriff: "",
  detail: null,
  detailVersionen: [],
  externBrowse: null,
  externEintraege: [],
  uploads: [],
  speicher: null,
  version: "",
});

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
    auswahl.leeren();
    await ladeMit(() => api.papierkorb());
    ladeSpeicher();
  } catch (f) {
    zustand.fehler = (f as Error).message;
  }
}

// Nur das jeweils neueste Laden darf das Ergebnis schreiben (verhindert, dass
// eine aeltere, langsamere Antwort eine neuere ueberschreibt).
let lauf = 0;

export const aktuellerOrdner = (): string | null => zustand.pfad[zustand.pfad.length - 1].id;

// In diesen Ansichten darf angelegt, hochgeladen, verschoben und umbenannt werden.
export const istSchreibbar = (): boolean => zustand.bereich === "dateien";

function detailSchliessen(): void {
  zustand.detail = null;
  zustand.detailVersionen = [];
}

// --- Laden ------------------------------------------------------------------

async function ladeMit(quelle: () => Promise<Knoten[]>): Promise<void> {
  const meins = ++lauf;
  zustand.laden = true;
  zustand.fehler = "";
  try {
    const ergebnis = await quelle();
    if (meins !== lauf) return;
    zustand.eintraege = ergebnis;
    auswahl.beschraenkeAuf(ergebnis.map((k) => k.id));
    if (zustand.detail && !ergebnis.some((k) => k.id === zustand.detail!.id)) detailSchliessen();
    if (zustand.speicher === null) ladeSpeicher();
  } catch (f) {
    if (meins === lauf) zustand.fehler = (f as Error).message;
  } finally {
    if (meins === lauf) zustand.laden = false;
  }
}

export function ladeOrdner(): Promise<void> {
  return ladeMit(() => api.kinder(aktuellerOrdner()));
}

// --- Bereichswechsel --------------------------------------------------------

export function zeigeDateien(): void {
  zustand.bereich = "dateien";
  zustand.pfad = [{ id: null, name: "Meine Dateien" }];
  zustand.externBrowse = null;
  zustand.suchbegriff = "";
  auswahl.leeren();
  detailSchliessen();
  ladeOrdner();
}

export function zeigePapierkorb(): void {
  zustand.bereich = "papierkorb";
  zustand.externBrowse = null;
  auswahl.leeren();
  detailSchliessen();
  ladeMit(() => api.papierkorb());
}

export function zeigeExterneQuellen(): void {
  zustand.bereich = "extern";
  zustand.externBrowse = null;
  auswahl.leeren();
  detailSchliessen();
  // Externe Quellen sind Knoten vom Typ "extern" auf oberster Ebene.
  ladeMit(async () => (await api.kinder(null)).filter((k) => k.typ === "extern"));
}

export async function starteSuche(): Promise<void> {
  const q = zustand.suchbegriff.trim();
  if (!q) {
    zeigeDateien();
    return;
  }
  zustand.bereich = "suche";
  zustand.externBrowse = null;
  auswahl.leeren();
  detailSchliessen();
  await ladeMit(() => api.suchen(q));
}

// --- Navigation im Ordnerbaum ----------------------------------------------

export function oeffneOrdner(k: Knoten): void {
  zustand.pfad = [...zustand.pfad, { id: k.id, name: k.name }];
  auswahl.leeren();
  detailSchliessen();
  ladeOrdner();
}

export function breadcrumbGehe(index: number): void {
  zustand.pfad = zustand.pfad.slice(0, index + 1);
  auswahl.leeren();
  detailSchliessen();
  ladeOrdner();
}

// --- Detail-Pane ------------------------------------------------------------

export async function zeigeDetail(k: Knoten): Promise<void> {
  zustand.detail = k;
  zustand.detailVersionen = [];
  if (k.typ === "datei") {
    // Bewusst NICHT den Lade-Zaehler 'lauf' anfassen - das wuerde ein laufendes
    // Listen-Laden faelschlich als veraltet verwerfen. Stattdessen ueber die
    // Detail-Id absichern: nur schreiben, wenn noch dieselbe Datei offen ist.
    try {
      const v = await api.versionen(k.id);
      if (zustand.detail?.id === k.id) zustand.detailVersionen = v;
    } catch {
      // Detail bleibt auch ohne Versionsliste nutzbar.
    }
  }
}

export function schliesseDetail(): void {
  detailSchliessen();
}

// --- Oeffnen (Doppelklick) --------------------------------------------------

export function oeffnen(k: Knoten): void {
  if (k.typ === "ordner") oeffneOrdner(k);
  else if (k.typ === "extern") externOeffnen(k);
  else herunterladen(k);
}

// --- Externe read-only Quelle ----------------------------------------------

export function externOeffnen(k: Knoten): void {
  zustand.bereich = "extern";
  zustand.externBrowse = { knotenId: k.id, name: k.name, unterpfad: [] };
  auswahl.leeren();
  detailSchliessen();
  ladeExtern();
}

export async function ladeExtern(): Promise<void> {
  const b = zustand.externBrowse;
  if (!b) return;
  const meins = ++lauf;
  zustand.laden = true;
  zustand.fehler = "";
  try {
    const ergebnis = await api.externAuflisten(b.knotenId, b.unterpfad.join("/"));
    if (meins === lauf) zustand.externEintraege = ergebnis;
  } catch (f) {
    if (meins === lauf) zustand.fehler = (f as Error).message;
  } finally {
    if (meins === lauf) zustand.laden = false;
  }
}

export function externGehe(e: ExternEintrag): void {
  const b = zustand.externBrowse;
  if (!b) return;
  if (e.ist_ordner) {
    b.unterpfad = [...b.unterpfad, e.name];
    ladeExtern();
  } else {
    externRunter(e);
  }
}

export async function externRunter(e: ExternEintrag): Promise<void> {
  const b = zustand.externBrowse;
  if (!b) return;
  const rel = [...b.unterpfad, e.name].join("/");
  try {
    await api.externHerunterladen(b.knotenId, rel, e.name);
  } catch (f) {
    zustand.fehler = (f as Error).message;
  }
}

export function externBreadcrumb(index: number): void {
  const b = zustand.externBrowse;
  if (!b) return;
  if (index < 0) {
    zeigeExterneQuellen();
    return;
  }
  b.unterpfad = b.unterpfad.slice(0, index);
  ladeExtern();
}

// --- Schreibaktionen --------------------------------------------------------

export async function ordnerAnlegen(name: string): Promise<void> {
  try {
    await api.ordnerAnlegen(name, aktuellerOrdner());
    await ladeOrdner();
  } catch (f) {
    zustand.fehler = (f as Error).message;
  }
}

export async function umbenennen(k: Knoten, name: string): Promise<void> {
  const sauber = name.trim();
  if (!sauber || sauber === k.name) return;
  try {
    await api.umbenennen(k.id, sauber);
    if (zustand.detail?.id === k.id) zustand.detail = { ...zustand.detail, name: sauber };
    await ladeOrdner();
  } catch (f) {
    zustand.fehler = (f as Error).message;
  }
}

export async function verschiebe(ids: string[], zielId: string | null): Promise<void> {
  try {
    for (const id of ids) {
      if (id === zielId) continue;
      await api.verschieben(id, zielId);
    }
    auswahl.leeren();
    await ladeOrdner();
  } catch (f) {
    zustand.fehler = (f as Error).message;
  }
}

export async function loeschen(ids: string[]): Promise<void> {
  try {
    for (const id of ids) await api.loeschen(id);
    auswahl.leeren();
    detailSchliessen();
    await ladeOrdner();
  } catch (f) {
    zustand.fehler = (f as Error).message;
  }
}

export async function wiederherstellen(ids: string[]): Promise<void> {
  try {
    for (const id of ids) await api.wiederherstellen(id);
    auswahl.leeren();
    await ladeMit(() => api.papierkorb());
  } catch (f) {
    zustand.fehler = (f as Error).message;
  }
}

export async function herunterladen(k: Knoten): Promise<void> {
  try {
    await api.herunterladen(k);
  } catch (f) {
    zustand.fehler = (f as Error).message;
  }
}

let aktuellerUploadGriff: (() => void) | null = null;
let uploadAbgebrochen = false;

export function uploadStoppen(): void {
  uploadAbgebrochen = true;
  aktuellerUploadGriff?.();
}

export async function hochladen(dateien: FileList | File[] | null): Promise<void> {
  if (!dateien) return;
  const liste = Array.from(dateien);
  if (liste.length === 0) return;
  const ordner = aktuellerOrdner();
  zustand.fehler = "";
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
        zustand.fehler = (f as Error).message;
        break;
      }
    }
  } finally {
    aktuellerUploadGriff = null;
    zustand.uploads = [];
    await ladeOrdner();
    ladeSpeicher();
  }
}

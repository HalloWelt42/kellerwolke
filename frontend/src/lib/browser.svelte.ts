import * as api from "./api";
import { erzeugeAuswahl, type Auswahl } from "./auswahl.svelte";
import { leererFilter, type Filterzustand } from "./filter";
import { eindeutigeId } from "./id";
import type { ExternEintrag, Knoten, Version } from "./types";

// Eine instanziierbare Browsing-Flaeche: haelt Pfad, Liste, Auswahl, Filter,
// Sortierung, Detail und alle Lade-/Navigations-/Schreibaktionen. Die
// Einzelansicht ist eine Instanz, jede Splitscreen-Pane eine weitere - alle
// laufen denselben Code mit EIGENEM Zustand. Frueher war das ein globaler
// Singleton in zustand.svelte.ts; genau deshalb musste der Splitscreen alles
// duplizieren. Backend-Funktionen kommen unveraendert aus api.ts.

export type Bereich = "dateien" | "extern" | "papierkorb" | "suche" | "favoriten" | "geteilt";
export type Ansicht = "liste" | "grid";
export type SortKey = "name" | "groesse" | "geaendert";
export type SortRichtung = "auf" | "ab";

export interface Pfadteil {
  id: string | null;
  name: string;
}

export class Browser {
  readonly id = eindeutigeId();
  readonly auswahl: Auswahl = erzeugeAuswahl();

  bereich = $state<Bereich>("dateien");
  pfad = $state<Pfadteil[]>([{ id: null, name: "Meine Dateien" }]);
  eintraege = $state<Knoten[]>([]);
  laden = $state(false);
  fehler = $state("");
  suchbegriff = $state("");
  detail = $state<Knoten | null>(null);
  detailVersionen = $state<Version[]>([]);
  externBrowse = $state<{ knotenId: string; name: string; unterpfad: string[] } | null>(null);
  externEintraege = $state<ExternEintrag[]>([]);
  geteiltPfad = $state<Pfadteil[]>([]);
  filter = $state<Filterzustand>(leererFilter());
  sortKey = $state<SortKey>("name");
  sortRichtung = $state<SortRichtung>("auf");
  ansicht = $state<Ansicht>("liste");
  scrollTop = $state(0);

  // Nur das jeweils neueste Laden darf das Ergebnis schreiben (verhindert, dass
  // eine aeltere, langsamere Antwort eine neuere ueberschreibt). Pro Instanz.
  private lauf = 0;

  get aktuellerOrdner(): string | null {
    return this.pfad[this.pfad.length - 1].id;
  }

  // In diesen Ansichten darf angelegt, hochgeladen, verschoben und umbenannt werden.
  get istSchreibbar(): boolean {
    return this.bereich === "dateien";
  }

  private detailSchliessen = (): void => {
    this.detail = null;
    this.detailVersionen = [];
  };

  setzeSortierung = (key: SortKey): void => {
    if (this.sortKey === key) {
      this.sortRichtung = this.sortRichtung === "auf" ? "ab" : "auf";
    } else {
      this.sortKey = key;
      this.sortRichtung = "auf";
    }
  };

  // --- Laden ----------------------------------------------------------------

  ladeMit = async (quelle: () => Promise<Knoten[]>): Promise<void> => {
    const meins = ++this.lauf;
    this.laden = true;
    this.fehler = "";
    try {
      const ergebnis = await quelle();
      if (meins !== this.lauf) return;
      this.eintraege = ergebnis;
      this.auswahl.beschraenkeAuf(ergebnis.map((k) => k.id));
      if (this.detail && !ergebnis.some((k) => k.id === this.detail!.id)) this.detailSchliessen();
    } catch (f) {
      if (meins === this.lauf) this.fehler = (f as Error).message;
    } finally {
      if (meins === this.lauf) this.laden = false;
    }
  };

  ladeOrdner = (): Promise<void> => this.ladeMit(() => api.kinder(this.aktuellerOrdner));

  // Laedt die aktuelle Ansicht passend zum Bereich neu (fuer den Live-Abgleich).
  aktualisiere = (): void => {
    if (this.bereich === "dateien") this.ladeOrdner();
    else if (this.bereich === "favoriten") this.ladeMit(() => api.favoriten());
    else if (this.bereich === "geteilt") {
      const p = this.geteiltPfad;
      this.ladeMit(() => (p.length ? api.geteiltKinder(p[p.length - 1].id as string) : api.geteilt()));
    } else if (this.bereich === "papierkorb") this.ladeMit(() => api.papierkorb());
    else if (this.bereich === "suche" && this.suchbegriff) this.ladeMit(() => api.suchen(this.suchbegriff));
    else if (this.bereich === "extern" && this.externBrowse) this.ladeExtern();
    else if (this.bereich === "extern")
      this.ladeMit(async () => (await api.kinder(null)).filter((k) => k.typ === "extern"));
  };

  // --- Bereichswechsel ------------------------------------------------------

  zeigeDateien = (): void => {
    this.bereich = "dateien";
    this.pfad = [{ id: null, name: "Meine Dateien" }];
    this.externBrowse = null;
    this.suchbegriff = "";
    this.auswahl.leeren();
    this.detailSchliessen();
    this.ladeOrdner();
  };

  zeigeGeteilt = (): void => {
    this.bereich = "geteilt";
    this.externBrowse = null;
    this.geteiltPfad = [];
    this.suchbegriff = "";
    this.auswahl.leeren();
    this.detailSchliessen();
    this.ladeMit(() => api.geteilt());
  };

  geteiltOeffnen = (k: Knoten): void => {
    if (k.typ === "ordner") {
      this.geteiltPfad = [...this.geteiltPfad, { id: k.id, name: k.name }];
      this.auswahl.leeren();
      this.ladeMit(() => api.geteiltKinder(k.id));
    } else if (k.typ === "datei") {
      api.geteiltHerunterladen(k).catch((f) => (this.fehler = (f as Error).message));
    }
  };

  geteiltBreadcrumb = (index: number): void => {
    if (index < 0) {
      this.geteiltPfad = [];
      this.auswahl.leeren();
      this.ladeMit(() => api.geteilt());
      return;
    }
    const ziel = this.geteiltPfad[index];
    this.geteiltPfad = this.geteiltPfad.slice(0, index + 1);
    this.auswahl.leeren();
    this.ladeMit(() => api.geteiltKinder(ziel.id as string));
  };

  zeigeFavoriten = (): void => {
    this.bereich = "favoriten";
    this.externBrowse = null;
    this.suchbegriff = "";
    this.auswahl.leeren();
    this.detailSchliessen();
    this.ladeMit(() => api.favoriten());
  };

  favoritUmschalten = async (k: Knoten): Promise<void> => {
    try {
      await api.favoritSetzen(k.id, !k.favorit);
      if (this.bereich === "favoriten") await this.ladeMit(() => api.favoriten());
      else await this.ladeOrdner();
    } catch (f) {
      this.fehler = (f as Error).message;
    }
  };

  zeigePapierkorb = (): void => {
    this.bereich = "papierkorb";
    this.externBrowse = null;
    this.suchbegriff = "";
    this.auswahl.leeren();
    this.detailSchliessen();
    this.ladeMit(() => api.papierkorb());
  };

  zeigeExterneQuellen = (): void => {
    this.bereich = "extern";
    this.externBrowse = null;
    this.suchbegriff = "";
    this.auswahl.leeren();
    this.detailSchliessen();
    // Externe Quellen sind Knoten vom Typ "extern" auf oberster Ebene.
    this.ladeMit(async () => (await api.kinder(null)).filter((k) => k.typ === "extern"));
  };

  starteSuche = async (q: string): Promise<void> => {
    const sauber = q.trim();
    this.suchbegriff = sauber;
    if (!sauber) {
      this.zeigeDateien();
      return;
    }
    this.bereich = "suche";
    this.externBrowse = null;
    this.auswahl.leeren();
    this.detailSchliessen();
    await this.ladeMit(() => api.suchen(sauber));
  };

  // --- Navigation im Ordnerbaum ---------------------------------------------

  oeffneOrdner = (k: Knoten): void => {
    this.pfad = [...this.pfad, { id: k.id, name: k.name }];
    this.auswahl.leeren();
    this.detailSchliessen();
    this.ladeOrdner();
  };

  // Ordner frisch oeffnen (aus Favoriten/Suche): Bereich auf Dateien stellen und
  // den Pfad auf [Wurzel, Ordner] setzen (volle Ahnenkette ist dort nicht bekannt).
  oeffneOrdnerFrisch = (k: Knoten): void => {
    this.bereich = "dateien";
    this.pfad = [{ id: null, name: "Meine Dateien" }, { id: k.id, name: k.name }];
    this.auswahl.leeren();
    this.detailSchliessen();
    this.ladeOrdner();
  };

  // Direkt zu einem Ordner ueber die VOLLE Ahnenkette springen (z.B. aus einer
  // baumweiten Ansicht wie der Galerie) und optional eine Datei darin markieren
  // und ihr Detail anzeigen. `teile` ist die Ordnerkette OHNE Wurzel/Datei.
  oeffnePfad = async (teile: Pfadteil[], markiereId?: string): Promise<void> => {
    this.bereich = "dateien";
    this.externBrowse = null;
    this.pfad = [{ id: null, name: "Meine Dateien" }, ...teile];
    this.auswahl.leeren();
    this.detailSchliessen();
    await this.ladeOrdner();
    if (markiereId) {
      const k = this.eintraege.find((e) => e.id === markiereId);
      if (k) {
        this.auswahl.ersetze([markiereId]);
        this.zeigeDetail(k);
      }
    }
  };

  breadcrumbGehe = (index: number): void => {
    this.pfad = this.pfad.slice(0, index + 1);
    this.auswahl.leeren();
    this.detailSchliessen();
    this.ladeOrdner();
  };

  // --- Detail-Pane / Aktivieren ---------------------------------------------

  zeigeDetail = async (k: Knoten): Promise<void> => {
    this.detail = k;
    this.detailVersionen = [];
    if (k.typ === "datei") {
      // Bewusst NICHT den Lade-Zaehler anfassen - das wuerde ein laufendes
      // Listen-Laden faelschlich als veraltet verwerfen. Stattdessen ueber die
      // Detail-Id absichern: nur schreiben, wenn noch dieselbe Datei offen ist.
      try {
        const v = await api.versionen(k.id);
        if (this.detail?.id === k.id) this.detailVersionen = v;
      } catch {
        // Detail bleibt auch ohne Versionsliste nutzbar.
      }
    }
  };

  schliesseDetail = (): void => {
    this.detailSchliessen();
  };

  // Doppelklick/Aktivieren: Ordner navigiert, externer Knoten oeffnet, Datei
  // zeigt die Vorschau/Detail - NIE ein Download. Download ist ausschliesslich
  // die explizite Aktion herunterladen() (Knopf, Kontextmenue).
  oeffnen = (k: Knoten): void => {
    if (k.typ === "ordner") {
      if (this.bereich === "dateien") this.oeffneOrdner(k);
      else this.oeffneOrdnerFrisch(k);
    } else if (k.typ === "extern") {
      this.externOeffnen(k);
    } else if (this.bereich === "geteilt") {
      this.geteiltOeffnen(k);
    } else {
      this.zeigeDetail(k);
    }
  };

  // --- Externe Quellen ------------------------------------------------------

  externOeffnen = (k: Knoten): void => {
    this.bereich = "extern";
    this.externBrowse = { knotenId: k.id, name: k.name, unterpfad: [] };
    this.auswahl.leeren();
    this.detailSchliessen();
    this.ladeExtern();
  };

  ladeExtern = async (): Promise<void> => {
    const b = this.externBrowse;
    if (!b) return;
    const meins = ++this.lauf;
    this.laden = true;
    this.fehler = "";
    try {
      const ergebnis = await api.externAuflisten(b.knotenId, b.unterpfad.join("/"));
      if (meins === this.lauf) this.externEintraege = ergebnis;
    } catch (f) {
      if (meins === this.lauf) this.fehler = (f as Error).message;
    } finally {
      if (meins === this.lauf) this.laden = false;
    }
  };

  externGehe = (e: ExternEintrag): void => {
    const b = this.externBrowse;
    if (!b) return;
    if (e.ist_ordner) {
      b.unterpfad = [...b.unterpfad, e.name];
      this.ladeExtern();
    } else {
      this.externRunter(e);
    }
  };

  externRunter = async (e: ExternEintrag): Promise<void> => {
    const b = this.externBrowse;
    if (!b) return;
    const rel = [...b.unterpfad, e.name].join("/");
    try {
      await api.externHerunterladen(b.knotenId, rel, e.name);
    } catch (f) {
      this.fehler = (f as Error).message;
    }
  };

  externBreadcrumb = (index: number): void => {
    const b = this.externBrowse;
    if (!b) return;
    if (index < 0) {
      this.zeigeExterneQuellen();
      return;
    }
    b.unterpfad = b.unterpfad.slice(0, index);
    this.ladeExtern();
  };

  // --- Schreibaktionen ------------------------------------------------------

  ordnerAnlegen = async (name: string): Promise<void> => {
    // In einer schreibbaren externen Quelle landet das Anlegen dort, sonst im
    // eigenen Baum.
    const b = this.externBrowse;
    if (this.bereich === "extern" && b) {
      try {
        await api.externOrdnerAnlegen(b.knotenId, b.unterpfad.join("/"), name);
        await this.ladeExtern();
      } catch (f) {
        this.fehler = (f as Error).message;
      }
      return;
    }
    try {
      await api.ordnerAnlegen(name, this.aktuellerOrdner);
      await this.ladeOrdner();
    } catch (f) {
      this.fehler = (f as Error).message;
    }
  };

  umbenennen = async (k: Knoten, name: string): Promise<void> => {
    const sauber = name.trim();
    if (!sauber || sauber === k.name) return;
    try {
      await api.umbenennen(k.id, sauber);
      if (this.detail?.id === k.id) this.detail = { ...this.detail, name: sauber };
      await this.ladeOrdner();
    } catch (f) {
      this.fehler = (f as Error).message;
    }
  };

  verschiebe = async (ids: string[], zielId: string | null): Promise<void> => {
    try {
      for (const id of ids) {
        if (id === zielId) continue;
        await api.verschieben(id, zielId);
      }
      this.auswahl.leeren();
      await this.ladeOrdner();
    } catch (f) {
      this.fehler = (f as Error).message;
    }
  };

  loeschen = async (ids: string[]): Promise<void> => {
    try {
      for (const id of ids) await api.loeschen(id);
      this.auswahl.leeren();
      this.detailSchliessen();
      await this.ladeOrdner();
    } catch (f) {
      this.fehler = (f as Error).message;
    }
  };

  wiederherstellen = async (ids: string[]): Promise<void> => {
    try {
      for (const id of ids) await api.wiederherstellen(id);
      this.auswahl.leeren();
      await this.ladeMit(() => api.papierkorb());
    } catch (f) {
      this.fehler = (f as Error).message;
    }
  };

  endgueltigLoeschen = async (ids: string[]): Promise<void> => {
    try {
      for (const id of ids) await api.endgueltigLoeschen(id);
      this.auswahl.leeren();
      this.detailSchliessen();
      await this.ladeMit(() => api.papierkorb());
    } catch (f) {
      this.fehler = (f as Error).message;
    }
  };

  herunterladen = async (k: Knoten): Promise<void> => {
    try {
      await api.herunterladen(k);
    } catch (f) {
      this.fehler = (f as Error).message;
    }
  };

  zipHerunterladen = async (ids: string[], dateiname: string): Promise<void> => {
    try {
      await api.zipHerunterladen(ids, dateiname);
    } catch (f) {
      this.fehler = (f as Error).message;
    }
  };
}

export function erzeugeBrowser(): Browser {
  return new Browser();
}

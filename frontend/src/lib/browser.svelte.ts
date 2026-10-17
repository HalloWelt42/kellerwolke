import * as api from "./api";
import { erzeugeAuswahl, type Auswahl } from "./auswahl.svelte";
import { filterAktiv, leererFilter, passt, type Filterzustand } from "./filter";
import { eindeutigeId } from "./id";
import type { ExternEintrag, Knoten, Pfadteil, Version } from "./types";

// Eine instanziierbare Browsing-Fläche: hält Pfad, Liste, Auswahl, Filter,
// Sortierung, Detail und alle Lade-/Navigations-/Schreibaktionen. Die
// Einzelansicht ist eine Instanz, jede Splitscreen-Pane eine weitere - alle
// laufen denselben Code mit EIGENEM Zustand.
//
// Zwei Arten zu laden: ein Ortswechsel (anderer Ordner, anderer Bereich) zeigt
// das Ladeskelett und setzt Auswahl, Filter, Detail und Meldung zurück. Alles
// andere (eigene Aktionen, Live-Abgleich, Uploads) aktualisiert still über
// aktualisiere(): Liste, Bildlauf, Filter und eine laufende Eingabe bleiben,
// und zwar immer für den Bereich, den die Fläche gerade zeigt.

export type Bereich = "dateien" | "extern" | "papierkorb" | "suche" | "favoriten" | "geteilt";
export type Ansicht = "liste" | "grid";
export type SortKey = "name" | "groesse" | "geaendert";
export type SortRichtung = "auf" | "ab";
export type { Pfadteil };

// Was in einem Bereich erlaubt ist - eine Tabelle für Werkzeugleiste,
// Auswahlleiste, Kontextmenü und Ablegen. Der Server prüft ohnehin selbst.
export interface Rechte {
  anlegen: boolean; // Neuer Ordner, Hochladen, Ablegen
  umbenennen: boolean;
  verschieben: boolean;
  loeschen: boolean;
  teilen: boolean;
  favorit: boolean;
  zip: boolean; // mehrere als ZIP
  wiederherstellen: boolean;
  endgueltig: boolean;
}

const KEINE: Rechte = {
  anlegen: false, umbenennen: false, verschieben: false, loeschen: false, teilen: false,
  favorit: false, zip: false, wiederherstellen: false, endgueltig: false,
};

const RECHTE: Record<Bereich, Rechte> = {
  dateien: { ...KEINE, anlegen: true, umbenennen: true, verschieben: true, loeschen: true, teilen: true, favorit: true, zip: true },
  favoriten: { ...KEINE, favorit: true, zip: true },
  suche: { ...KEINE, favorit: true, zip: true },
  geteilt: { ...KEINE },
  extern: { ...KEINE, favorit: true },
  papierkorb: { ...KEINE, wiederherstellen: true, endgueltig: true },
};

const WURZEL: Pfadteil = { id: null, name: "Meine Dateien" };

export class Browser {
  readonly id = eindeutigeId();
  readonly auswahl: Auswahl = erzeugeAuswahl();

  bereich = $state<Bereich>("dateien");
  pfad = $state<Pfadteil[]>([WURZEL]);
  eintraege = $state<Knoten[]>([]);
  laden = $state(false); // nur beim Ortswechsel: das Ladeskelett
  fehler = $state(""); // bleibt bis zum Ortswechsel oder Schliessen
  suchbegriff = $state("");
  detail = $state<Knoten | null>(null);
  detailVersionen = $state<Version[]>([]);
  detailPfad = $state<Pfadteil[] | null>(null); // Ordnerkette über dem Detail (eigene Knoten)
  externBrowse = $state<{ knotenId: string; name: string; unterpfad: string[] } | null>(null);
  externEintraege = $state<ExternEintrag[]>([]);
  geteiltPfad = $state<Pfadteil[]>([]);
  filter = $state<Filterzustand>(leererFilter());
  sortKey = $state<SortKey>("name");
  sortRichtung = $state<SortRichtung>("auf");
  ansicht = $state<Ansicht>("liste");
  // Verschieben über Navigation: gemerkte Auswahl, Ziel ist der Ordner, in dem man "Hierher" wählt.
  verschiebeIds = $state<string[] | null>(null);

  // Was die Fläche zeigt, in der Reihenfolge, in der sie es zeigt (Filter und
  // Sortierung); Ordner und Externe immer vor Dateien. Eine Stelle für Liste,
  // Auswahl, Blättern in der Vollansicht und die Titelliste des Players.
  // Hauptdateien, deren Begleiter gerade unter ihnen stehen (je Fläche, bleibt beim Ortswechsel).
  offeneGruppen = $state<Record<string, boolean>>({});

  // In der Liste stehen Begleitdateien direkt unter ihrer Hauptdatei, wenn deren Gruppe offen ist, sonst gar nicht;
  // liegt die Hauptdatei nicht in der Liste (Suche, Filter), stehen sie für sich.
  sichtbar = $derived.by(() => {
    const quelle = filterAktiv(this.filter) ? this.eintraege.filter((k) => passt(k.name, this.filter)) : this.eintraege;
    const rang = (k: Knoten) => (k.typ === "ordner" ? 0 : k.typ === "extern" ? 1 : 2);
    const key = this.sortKey;
    const dir = this.sortRichtung === "auf" ? 1 : -1;
    const sortiert = [...quelle].sort((a, b) => {
      if (rang(a) !== rang(b)) return rang(a) - rang(b);
      let v: number;
      if (key === "groesse") v = (a.groesse ?? 0) - (b.groesse ?? 0);
      else if (key === "geaendert") v = new Date(a.geaendert_am).getTime() - new Date(b.geaendert_am).getTime();
      else v = a.name.localeCompare(b.name, "de", { sensitivity: "base", numeric: true });
      return v * dir;
    });
    // Kacheln: Begleiter stehen ohnehin neben ihrer Hauptdatei (gleicher Stamm); im Papierkorb ist jede Zeile für sich.
    if (this.ansicht !== "liste" || this.bereich === "papierkorb") return sortiert;
    const da = new Set(sortiert.map((k) => k.id));
    const begleiter = new Map<string, Knoten[]>();
    for (const k of sortiert) {
      if (k.haupt_id && da.has(k.haupt_id)) begleiter.set(k.haupt_id, [...(begleiter.get(k.haupt_id) ?? []), k]);
    }
    const aus: Knoten[] = [];
    for (const k of sortiert) {
      if (k.haupt_id && da.has(k.haupt_id)) continue;
      aus.push(k);
      if (this.offeneGruppen[k.id]) aus.push(...(begleiter.get(k.id) ?? []));
    }
    return aus;
  });

  gruppeUmschalten(id: string): void {
    this.offeneGruppen = { ...this.offeneGruppen, [id]: !this.offeneGruppen[id] };
  }

  // Die Begleiter einer Hauptdatei in dieser Fläche (Detail, Blatt am Telefon).
  begleiterVon(id: string): Knoten[] {
    return this.eintraege.filter((k) => k.haupt_id === id).sort((a, b) => a.name.localeCompare(b.name, "de"));
  }

  // Nur das jeweils neueste Laden darf das Ergebnis schreiben (verhindert, dass
  // eine ältere, langsamere Antwort eine neuere überschreibt). Pro Instanz.
  private lauf = 0;

  get aktuellerOrdner(): string | null {
    return this.pfad[this.pfad.length - 1].id;
  }

  get rechte(): Rechte {
    // Externe Quellen: die Übersicht erlaubt den Stern, darin ist alles nur lesbar.
    return this.bereich === "extern" && this.externBrowse ? KEINE : RECHTE[this.bereich];
  }

  // In diesen Ansichten darf angelegt, hochgeladen und abgelegt werden.
  get istSchreibbar(): boolean {
    return this.rechte.anlegen;
  }

  // Name des Ordners, in dem Neues landet (für Hinweise beim Ablegen).
  get zielName(): string {
    return this.pfad[this.pfad.length - 1].name;
  }

  private detailSchliessen = (): void => {
    this.detail = null;
    this.detailVersionen = [];
    this.detailPfad = null;
  };

  // Gemeinsamer Anfang jedes Ortswechsels.
  private ortswechsel = (): void => {
    this.auswahl.leeren();
    this.detailSchliessen();
    this.filter = leererFilter();
    this.fehler = "";
  };

  setzeSortierung = (key: SortKey): void => {
    if (this.sortKey === key) {
      this.sortRichtung = this.sortRichtung === "auf" ? "ab" : "auf";
    } else {
      this.sortKey = key;
      this.sortRichtung = "auf";
    }
  };

  fehlerSchliessen = (): void => {
    this.fehler = "";
  };

  // Zurück in den Anfangszustand, ohne zu laden (beim Verlassen des Kontos).
  zuruecksetzen = (): void => {
    this.lauf++;
    this.bereich = "dateien";
    this.pfad = [WURZEL];
    this.eintraege = [];
    this.externBrowse = null;
    this.externEintraege = [];
    this.geteiltPfad = [];
    this.suchbegriff = "";
    this.verschiebeIds = null;
    this.laden = false;
    this.ortswechsel();
  };

  // --- Laden ----------------------------------------------------------------

  private ladeMit = async (quelle: () => Promise<Knoten[]>, still: boolean): Promise<void> => {
    const meins = ++this.lauf;
    if (!still) this.laden = true;
    try {
      const ergebnis = await quelle();
      if (meins !== this.lauf) return;
      this.eintraege = ergebnis;
      this.auswahl.beschraenkeAuf(ergebnis.map((k) => k.id));
      this.detailNachziehen(ergebnis);
    } catch (f) {
      if (meins !== this.lauf) return;
      // Nach einem Ortswechsel gehört die alte Liste nicht mehr hierher.
      if (!still) this.eintraege = [];
      // Ohne Verbindung meldet das Band der Oberfläche; die Fläche schweigt dazu.
      if ((f as api.ApiFehler).status !== 0) this.fehler = (f as Error).message;
    } finally {
      if (meins === this.lauf) this.laden = false;
    }
  };

  // Das offene Detail an den neuen Stand anpassen: weg, wenn der Eintrag fehlt,
  // sonst frische Werte und bei neuer Version auch die Versionsliste.
  private detailNachziehen = (ergebnis: Knoten[]): void => {
    const d = this.detail;
    if (!d) return;
    const neu = ergebnis.find((k) => k.id === d.id);
    if (!neu) {
      this.detailSchliessen();
      return;
    }
    const neueVersion = neu.etag !== d.etag;
    this.detail = neu;
    if (neueVersion) this.versionenLaden(neu);
  };

  // Die Quelle des Bereichs, den die Fläche gerade zeigt.
  private quelle = (): (() => Promise<Knoten[]>) | null => {
    switch (this.bereich) {
      case "dateien": {
        const ordner = this.aktuellerOrdner;
        return () => api.kinder(ordner);
      }
      case "favoriten":
        return () => api.favoriten();
      case "papierkorb":
        return () => api.papierkorb();
      case "suche": {
        const q = this.suchbegriff;
        return q ? () => api.suchen(q) : null;
      }
      case "geteilt": {
        const p = this.geteiltPfad;
        return p.length ? () => api.geteiltKinder(p[p.length - 1].id as string) : () => api.geteilt();
      }
      case "extern":
        return this.externBrowse ? null : async () => (await api.kinder(null)).filter((k) => k.typ === "extern");
    }
  };

  private ortLaden = (): Promise<void> => {
    const q = this.quelle();
    if (q) return this.ladeMit(q, false);
    if (this.bereich === "extern" && this.externBrowse) return this.ladeExtern(false);
    return Promise.resolve();
  };

  // Still neu laden, passend zum Bereich (Aktionen, Live-Abgleich, Uploads).
  aktualisiere = (): Promise<void> => {
    const q = this.quelle();
    if (q) return this.ladeMit(q, true);
    if (this.bereich === "extern" && this.externBrowse) return this.ladeExtern(true);
    return Promise.resolve();
  };

  // --- Bereichswechsel ------------------------------------------------------

  private bereichOeffnen = (bereich: Bereich): Promise<void> => {
    this.bereich = bereich;
    this.externBrowse = null;
    this.geteiltPfad = [];
    this.verschiebeIds = null;
    if (bereich !== "suche") this.suchbegriff = "";
    this.ortswechsel();
    return this.ortLaden();
  };

  zeigeDateien = (): Promise<void> => {
    this.pfad = [WURZEL];
    return this.bereichOeffnen("dateien");
  };
  zeigeGeteilt = (): Promise<void> => this.bereichOeffnen("geteilt");
  zeigeFavoriten = (): Promise<void> => this.bereichOeffnen("favoriten");
  zeigePapierkorb = (): Promise<void> => this.bereichOeffnen("papierkorb");
  zeigeExterneQuellen = (): Promise<void> => this.bereichOeffnen("extern");

  starteSuche = (q: string): Promise<void> => {
    const sauber = q.trim();
    if (!sauber) return this.zeigeDateien();
    this.suchbegriff = sauber;
    return this.bereichOeffnen("suche");
  };

  geteiltOeffnen = (k: Knoten): void => {
    if (k.typ === "ordner") {
      this.geteiltPfad = [...this.geteiltPfad, { id: k.id, name: k.name }];
      this.ortswechsel();
      this.ortLaden();
    } else {
      this.zeigeDetail(k);
    }
  };

  geteiltBreadcrumb = (index: number): void => {
    this.geteiltPfad = index < 0 ? [] : this.geteiltPfad.slice(0, index + 1);
    this.ortswechsel();
    this.ortLaden();
  };

  favoritUmschalten = async (k: Knoten): Promise<void> => {
    try {
      await api.favoritSetzen(k.id, !k.favorit);
      await this.aktualisiere();
    } catch (f) {
      this.fehler = (f as Error).message;
    }
  };

  // --- Navigation im Ordnerbaum ---------------------------------------------

  private ordnerZeigen = (pfad: Pfadteil[]): Promise<void> => {
    this.bereich = "dateien";
    this.externBrowse = null;
    this.suchbegriff = "";
    this.pfad = pfad;
    this.ortswechsel();
    return this.ortLaden();
  };

  oeffneOrdner = (k: Knoten): Promise<void> => this.ordnerZeigen([...this.pfad, { id: k.id, name: k.name }]);

  // Ordner aus Favoriten oder Suche: mit voller Ahnenkette vom Server.
  oeffneOrdnerMitPfad = async (k: Knoten): Promise<void> => {
    let kette: Pfadteil[] = [];
    try {
      kette = await api.pfadVon(k.id);
    } catch {
      // ohne Kette bleibt der Breadcrumb kurz, der Ordner öffnet trotzdem
    }
    await this.ordnerZeigen([WURZEL, ...kette, { id: k.id, name: k.name }]);
  };

  // Direkt zu einem Ordner über die Ahnenkette springen (Medien, Player) und
  // optional eine Datei darin markieren und ihr Detail zeigen. `teile` ist die
  // Ordnerkette OHNE Wurzel und Datei.
  oeffnePfad = async (teile: Pfadteil[], markiereId?: string): Promise<void> => {
    this.verschiebeIds = null;
    await this.ordnerZeigen([WURZEL, ...teile]);
    if (markiereId) {
      const k = this.eintraege.find((e) => e.id === markiereId);
      if (k) {
        this.auswahl.ersetze([markiereId]);
        this.zeigeDetail(k);
      }
    }
  };

  breadcrumbGehe = (index: number): Promise<void> => this.ordnerZeigen(this.pfad.slice(0, index + 1));

  // --- Detail-Pane / Aktivieren ---------------------------------------------

  private versionenLaden = async (k: Knoten): Promise<void> => {
    try {
      const v = await api.versionen(k.id);
      if (this.detail?.id === k.id) this.detailVersionen = v;
    } catch {
      // Detail bleibt auch ohne Versionsliste nutzbar (geteilte Dateien haben keine).
    }
  };

  zeigeDetail = async (k: Knoten): Promise<void> => {
    this.detail = k;
    this.detailVersionen = [];
    this.detailPfad = null;
    if (k.typ === "datei") this.versionenLaden(k);
    if (this.bereich === "dateien") {
      this.detailPfad = this.pfad.slice(1);
    } else if (this.bereich !== "geteilt") {
      try {
        const kette = await api.pfadVon(k.id);
        if (this.detail?.id === k.id) this.detailPfad = kette;
      } catch {
        // Pfad ist Zusatzinfo
      }
    }
  };

  schliesseDetail = (): void => {
    this.detailSchliessen();
  };

  // Aktivieren (Doppelklick, "Öffnen"): Ordner navigiert, externer Knoten
  // öffnet, Datei zeigt das Detail - NIE ein Download. Medien öffnet die
  // Dateiliste selbst (Vollansicht, Wiedergabe), weil sie die Nachbarn kennt.
  oeffnen = (k: Knoten): void => {
    if (k.typ === "ordner") {
      if (this.bereich === "dateien") this.oeffneOrdner(k);
      else if (this.bereich === "geteilt") this.geteiltOeffnen(k);
      else this.oeffneOrdnerMitPfad(k);
    } else if (k.typ === "extern") {
      this.externOeffnen(k);
    } else {
      this.zeigeDetail(k);
    }
  };

  // --- Externe Quellen (nur lesbar) -----------------------------------------

  externOeffnen = (k: Knoten): void => {
    this.bereich = "extern";
    this.externBrowse = { knotenId: k.id, name: k.name, unterpfad: [] };
    this.externEintraege = [];
    this.ortswechsel();
    this.ladeExtern(false);
  };

  // Eine externe Quelle gleich an einer tieferen Stelle öffnen (aus einer Adresse).
  externOeffnenMit = (k: Knoten, unterpfad: string[]): void => {
    this.externOeffnen(k);
    if (unterpfad.length) this.externOrt(unterpfad);
  };

  ladeExtern = async (still = true): Promise<void> => {
    const b = this.externBrowse;
    if (!b) return;
    const meins = ++this.lauf;
    if (!still) this.laden = true;
    try {
      const ergebnis = await api.externAuflisten(b.knotenId, b.unterpfad.join("/"));
      if (meins === this.lauf) this.externEintraege = ergebnis;
    } catch (f) {
      if (meins === this.lauf) {
        this.externEintraege = [];
        if ((f as api.ApiFehler).status !== 0) this.fehler = (f as Error).message;
      }
    } finally {
      if (meins === this.lauf) this.laden = false;
    }
  };

  private externOrt = (unterpfad: string[]): void => {
    const b = this.externBrowse;
    if (!b) return;
    this.externBrowse = { ...b, unterpfad };
    this.externEintraege = [];
    this.ortswechsel();
    this.ladeExtern(false);
  };

  externGehe = (e: ExternEintrag): void => {
    const b = this.externBrowse;
    if (!b) return;
    if (e.ist_ordner) this.externOrt([...b.unterpfad, e.name]);
    else this.externRunter(e);
  };

  externRunter = (e: ExternEintrag): void => {
    const b = this.externBrowse;
    if (b) api.externHerunterladen(b.knotenId, [...b.unterpfad, e.name].join("/"), e.name);
  };

  externBreadcrumb = (index: number): void => {
    if (index < 0) this.zeigeExterneQuellen();
    else this.externOrt((this.externBrowse?.unterpfad ?? []).slice(0, index));
  };

  // --- Schreibaktionen ------------------------------------------------------

  ordnerAnlegen = async (name: string): Promise<void> => {
    if (!this.rechte.anlegen) return;
    try {
      await api.ordnerAnlegen(name, this.aktuellerOrdner);
      await this.aktualisiere();
    } catch (f) {
      this.fehler = (f as Error).message;
    }
  };

  umbenennen = async (k: Knoten, name: string): Promise<void> => {
    const sauber = name.trim();
    if (!sauber || sauber === k.name) return;
    try {
      await api.umbenennen(k.id, sauber);
      await this.aktualisiere();
    } catch (f) {
      this.fehler = (f as Error).message;
    }
  };

  // Verschiebt der Reihe nach; was scheitert, steht danach in der Meldung,
  // der Rest ist trotzdem verschoben.
  verschiebe = async (ids: string[], zielId: string | null): Promise<void> => {
    const fehlschlaege: string[] = [];
    for (const id of ids) {
      if (id === zielId) continue;
      try {
        await api.verschieben(id, zielId);
      } catch (f) {
        const name = this.eintraege.find((k) => k.id === id)?.name ?? "Ein Objekt";
        fehlschlaege.push(`${name}: ${(f as Error).message}`);
      }
    }
    this.auswahl.leeren();
    this.verschiebeIds = null;
    await this.aktualisiere();
    if (fehlschlaege.length) this.fehler = `Nicht verschoben - ${fehlschlaege.join("; ")}`;
  };

  verschiebenBeginnen = (ids: string[]): void => {
    if (ids.length) this.verschiebeIds = [...ids];
  };

  verschiebenHierher = (): Promise<void> => {
    const ids = this.verschiebeIds ?? [];
    return this.verschiebe(ids, this.aktuellerOrdner);
  };

  verschiebenAbbrechen = (): void => {
    this.verschiebeIds = null;
  };

  loeschen = async (ids: string[]): Promise<void> => {
    try {
      for (const id of ids) await api.loeschen(id);
    } catch (f) {
      this.fehler = (f as Error).message;
    }
    this.auswahl.leeren();
    await this.aktualisiere();
  };

  wiederherstellen = async (ids: string[]): Promise<void> => {
    try {
      for (const id of ids) await api.wiederherstellen(id);
    } catch (f) {
      this.fehler = (f as Error).message;
    }
    this.auswahl.leeren();
    await this.aktualisiere();
  };

  endgueltigLoeschen = async (ids: string[]): Promise<void> => {
    try {
      for (const id of ids) await api.endgueltigLoeschen(id);
    } catch (f) {
      this.fehler = (f as Error).message;
    }
    this.auswahl.leeren();
    await this.aktualisiere();
  };

  herunterladen = (k: Knoten): void => {
    api.herunterladen(k);
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

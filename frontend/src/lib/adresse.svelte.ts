// Die Adresse im Browser zeigt, wo man ist, mit echten Pfaden:
//   /dateien/Apps/Probe            Ordner in "Meine Dateien"
//   /dateien/Apps/Probe/notiz.txt  Ordner mit gezeigter Datei
//   /favoriten  /geteilt  /papierkorb  /medien  /suche?q=...
//   /extern/<Quelle>/<Unterpfad>   externe Quelle
//   /einstellungen/<Seite>         Verwaltung (am Rechner); am Telefon dazu /mehr
// Zurück und Vor im Browser führen dorthin zurück, und jede Adresse lässt sich als Link öffnen. Gespiegelt wird die
// Hauptfläche; in der geteilten Ansicht bleibt die Adresse beim Hauptort. Ein Ortswechsel legt einen neuen Eintrag in
// den Verlauf, eine andere gezeigte Datei im selben Ordner ersetzt ihn nur.
import * as api from "./api";
import { ansicht, waehleAnsicht } from "./ansicht.svelte";
import { auth } from "./auth.svelte";
import { geraet } from "./geraet.svelte";
import { mobil, zeigeReiter, zeigeSeite } from "./mobil/mobil.svelte";
import { EINSTELLUNGS_SEITEN, verwaltung, type EinstellungsSeite } from "./verwaltung.svelte";
import { haupt } from "./zustand.svelte";

export type Ort =
  | { art: "dateien"; teile: string[]; datei?: string }
  | { art: "extern"; teile: string[] } // erster Teil: Name der Quelle, danach der Unterpfad
  | { art: "suche"; q: string }
  | { art: "einstellungen"; seite: EinstellungsSeite | null }
  | { art: "favoriten" | "geteilt" | "papierkorb" | "medien" | "mehr" };

const EINFACH = ["favoriten", "geteilt", "papierkorb", "medien", "mehr"] as const;

function kodiert(teile: string[]): string {
  return teile.map(encodeURIComponent).join("/");
}

export function adresseVon(ort: Ort): string {
  switch (ort.art) {
    case "dateien": {
      const teile = ort.datei ? [...ort.teile, ort.datei] : ort.teile;
      return teile.length ? `/dateien/${kodiert(teile)}` : "/dateien";
    }
    case "extern":
      return ort.teile.length ? `/extern/${kodiert(ort.teile)}` : "/extern";
    case "suche":
      return `/suche?q=${encodeURIComponent(ort.q)}`;
    case "einstellungen":
      return ort.seite ? `/einstellungen/${ort.seite}` : "/einstellungen";
    default:
      return `/${ort.art}`;
  }
}

// Adresse eines Ordners oder einer Datei in "Meine Dateien" ("Apps/Probe"), etwa für Links in der Verwaltung.
export function dateienAdresse(pfad: string): string {
  return adresseVon({ art: "dateien", teile: pfad.split("/").filter(Boolean) });
}

export function ortAus(pfadname: string, suche: string): Ort {
  const teile = pfadname
    .split("/")
    .filter(Boolean)
    .map((t) => {
      try {
        return decodeURIComponent(t);
      } catch {
        return t;
      }
    });
  const [kopf, ...rest] = teile;
  if ((EINFACH as readonly string[]).includes(kopf)) return { art: kopf as (typeof EINFACH)[number] };
  if (kopf === "extern") return { art: "extern", teile: rest };
  if (kopf === "suche") return { art: "suche", q: new URLSearchParams(suche).get("q") ?? "" };
  if (kopf === "einstellungen") {
    const seite = EINSTELLUNGS_SEITEN.find((s) => s === rest[0]) ?? null;
    return { art: "einstellungen", seite };
  }
  return { art: "dateien", teile: kopf === "dateien" ? rest : [] };
}

// Wo man gerade ist, aus dem Zustand der Oberfläche.
function aktuellerOrt(): Ort {
  if (!geraet.mobil && verwaltung.offen) return { art: "einstellungen", seite: verwaltung.seite };
  if (geraet.mobil ? mobil.reiter === "medien" && !mobil.seite : ansicht.aktiv === "medien") return { art: "medien" };
  if (geraet.mobil && mobil.reiter === "mehr" && !mobil.seite) return { art: "mehr" };
  switch (haupt.bereich) {
    case "dateien": {
      const d = haupt.detail;
      const imOrdner = d && d.typ === "datei" && (d.parent_id ?? null) === haupt.aktuellerOrdner;
      return { art: "dateien", teile: haupt.pfad.slice(1).map((p) => p.name), datei: imOrdner ? d.name : undefined };
    }
    case "extern":
      return { art: "extern", teile: haupt.externBrowse ? [haupt.externBrowse.name, ...haupt.externBrowse.unterpfad] : [] };
    case "suche":
      return { art: "suche", q: haupt.suchbegriff };
    default:
      return { art: haupt.bereich };
  }
}

// --- Zustand zur Adresse ---------------------------------------------------------------------------------------

let anwendend = true; // bis die erste Adresse angewandt ist, schreibt nichts in den Verlauf
let letzterOrt = "";

function ohneDatei(ort: Ort): string {
  return adresseVon(ort.art === "dateien" ? { ...ort, datei: undefined } : ort);
}

function schreiben(ort: Ort, ersetzen = false): void {
  const ziel = adresseVon(ort);
  const schluessel = ohneDatei(ort);
  if (ziel !== location.pathname + location.search) {
    if (ersetzen || schluessel === letzterOrt) history.replaceState(null, "", ziel);
    else history.pushState(null, "", ziel);
  }
  letzterOrt = schluessel;
}

// --- Adresse zum Zustand ---------------------------------------------------------------------------------------

async function dateienAnwenden(teile: string[]): Promise<void> {
  if (geraet.mobil) {
    mobil.reiter = "dateien";
    mobil.seite = null;
    mobil.blatt = null;
  }
  if (!teile.length) {
    await haupt.zeigeDateien();
    return;
  }
  try {
    const r = await api.pfadAufloesen(teile.join("/"));
    if (r.typ === "extern") await externAnwenden([r.name]);
    else if (r.typ === "ordner") await haupt.oeffnePfad([...r.kette, { id: r.id, name: r.name }]);
    else await haupt.oeffnePfad(r.kette, r.id);
  } catch (f) {
    await haupt.zeigeDateien();
    haupt.fehler = (f as api.ApiFehler).status === 404 ? `${teile.join("/")} gibt es nicht (mehr).` : (f as Error).message;
  }
}

async function externAnwenden(teile: string[]): Promise<void> {
  await haupt.zeigeExterneQuellen();
  if (!teile.length) return;
  const quelle = haupt.eintraege.find((k) => k.typ === "extern" && k.name.toLowerCase() === teile[0].toLowerCase());
  if (quelle) haupt.externOeffnenMit(quelle, teile.slice(1));
  else haupt.fehler = `Die externe Quelle ${teile[0]} gibt es nicht.`;
}

async function anwenden(ort: Ort): Promise<void> {
  anwendend = true;
  try {
    if (ort.art === "einstellungen" && !geraet.mobil) {
      verwaltung.seite = ort.seite;
      verwaltung.offen = true;
      return;
    }
    verwaltung.offen = false;
    if (ort.art === "medien") {
      if (geraet.mobil) zeigeReiter("medien");
      else waehleAnsicht("medien");
      return;
    }
    if (!geraet.mobil) waehleAnsicht("dateien");
    switch (ort.art) {
      case "dateien":
        await dateienAnwenden(ort.teile);
        break;
      case "extern":
        if (geraet.mobil) await dateienAnwenden([]);
        else await externAnwenden(ort.teile);
        break;
      case "suche":
        if (geraet.mobil) mobil.seite = "suche";
        await haupt.starteSuche(ort.q);
        break;
      case "favoriten":
        if (geraet.mobil) zeigeReiter("favoriten");
        else await haupt.zeigeFavoriten();
        break;
      case "geteilt":
        if (geraet.mobil) zeigeSeite("geteilt");
        else await haupt.zeigeGeteilt();
        break;
      case "papierkorb":
        if (geraet.mobil) zeigeSeite("papierkorb");
        else await haupt.zeigePapierkorb();
        break;
      default: // "mehr" und die Verwaltung am Telefon
        if (geraet.mobil) zeigeReiter("mehr");
        else await haupt.zeigeDateien();
    }
  } finally {
    anwendend = false;
    schreiben(aktuellerOrt(), true);
  }
}

// Die Adresse im Browser anwenden (nach der Anmeldung und bei Zurück oder Vor).
export function adresseAnwenden(): Promise<void> {
  return anwenden(ortAus(location.pathname, location.search));
}

// In der Oberfläche zu einer Adresse gehen, wie ein Link (neuer Eintrag im Verlauf).
export function navigiere(ziel: string): void {
  const url = new URL(ziel, location.origin);
  history.pushState(null, "", url.pathname + url.search);
  void anwenden(ortAus(url.pathname, url.search));
}

export function adresseStarten(): () => void {
  const aufraeumen = $effect.root(() => {
    $effect(() => {
      if (!auth.angemeldet) return;
      const ort = aktuellerOrt();
      if (!anwendend) schreiben(ort);
    });
  });
  const zurueckVor = () => {
    if (auth.angemeldet) void adresseAnwenden();
  };
  addEventListener("popstate", zurueckVor);
  return () => {
    aufraeumen();
    removeEventListener("popstate", zurueckVor);
  };
}

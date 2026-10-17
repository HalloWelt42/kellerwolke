// Rund ums Koppeln eines Geräts: Code anzeigen und lesen, Link für den QR-Code, Art und Namensvorschlag,
// Texte zu "zuletzt gesehen". Entwurf: mockups/geraete.html und mockups/geraete-mobil.html.
import type { Geraet, GeraeteArt } from "./types";
import { datum } from "./format";

export const CODE_LAENGE = 8;
export const ART_TEXT: Record<GeraeteArt, string> = { webapp: "Web-App", browser: "Browser" };
// Ab hier gilt ein Gerät als lange nicht gesehen; nur ein Hinweis, getrennt wird nichts von selbst.
export const LANGE_NICHT_TAGE = 60;
const LINK_MARKE = "koppeln=";

export function codeNormal(text: string): string {
  return text.replace(/[^0-9a-z]/gi, "").toUpperCase().slice(0, CODE_LAENGE);
}

export function codeAnzeige(code: string): string {
  return `${code.slice(0, 4)} ${code.slice(4)}`;
}

// Der QR-Code öffnet die Kellerwolke mit dem Code; nach dem # geht er nicht an den Server und in kein Protokoll.
export function koppelLink(code: string): string {
  return `${location.origin}/#${LINK_MARKE}${code}`;
}

// Kam die Seite über einen Koppel-Link, den Code einmal herausnehmen und aus der Adresse entfernen.
export function codeAusLinkNehmen(): string {
  const marke = location.hash.slice(1);
  if (!marke.startsWith(LINK_MARKE)) return "";
  history.replaceState(null, "", location.pathname + location.search);
  return codeNormal(marke.slice(LINK_MARKE.length));
}

// Als Web-App vom Home-Bildschirm gestartet oder im Browser; auf dem iPhone haben beide getrennte Speicher.
export function geraeteArt(): GeraeteArt {
  const eigenstaendig =
    window.matchMedia("(display-mode: standalone)").matches || (navigator as { standalone?: boolean }).standalone === true;
  return eigenstaendig ? "webapp" : "browser";
}

export function namensvorschlag(): string {
  const ua = navigator.userAgent;
  if (/iPad|Tablet/i.test(ua) || (/Macintosh/.test(ua) && navigator.maxTouchPoints > 1)) return "Tablet";
  if (/iPhone|Mobile/i.test(ua)) return "Telefon";
  if (/Android/i.test(ua)) return "Tablet";
  return "Rechner";
}

export function geraetSymbol(g: Pick<Geraet, "name">): string {
  if (/tablet/i.test(g.name)) return "fa-tablet-screen-button";
  if (/rechner|laptop/i.test(g.name)) return "fa-laptop";
  return "fa-mobile-screen";
}

function sekundenSeit(iso: string): number {
  return (Date.now() - new Date(iso).getTime()) / 1000;
}

export function langeNichtGesehen(g: Geraet): boolean {
  return !!g.zuletzt_am && sekundenSeit(g.zuletzt_am) > LANGE_NICHT_TAGE * 86400;
}

function anzahl(n: number, eins: string, mehr: string): string {
  return n === 1 ? eins : `${n} ${mehr}`;
}

export function zuletztText(g: Geraet): string {
  if (!g.zuletzt_am) return "noch nie gesehen";
  const s = sekundenSeit(g.zuletzt_am);
  if (s < 90) return "zuletzt gesehen gerade eben";
  if (s < 3600) return `zuletzt gesehen vor ${Math.round(s / 60)} Minuten`;
  if (s < 86400) return `zuletzt gesehen vor ${anzahl(Math.round(s / 3600), "einer Stunde", "Stunden")}`;
  if (s < 30 * 86400) return `zuletzt gesehen vor ${anzahl(Math.round(s / 86400), "einem Tag", "Tagen")}`;
  return `zuletzt am ${datum(g.zuletzt_am)}`;
}

// Restzeit eines Codes als m:ss.
export function restText(sekunden: number): string {
  const s = Math.max(0, Math.floor(sekunden));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

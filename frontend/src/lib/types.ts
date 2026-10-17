export interface Benutzer {
  id: string;
  name: string;
  kuerzel?: string | null;
  rolle: string;
  aktiv: boolean;
}

export type Knotentyp = "ordner" | "datei" | "extern";

export interface Knoten {
  id: string;
  besitzer_id: string;
  parent_id: string | null;
  name: string;
  typ: Knotentyp;
  etag: string | null;
  geloescht: boolean;
  erstellt_am: string;
  geaendert_am: string;
  // Groesse der aktuellen Version in Bytes; bei Ordnern/Externen null.
  groesse?: number | null;
  // Anzahl nicht geloeschter Kinder (fuer den Ordner-Zaehler).
  kinder_anzahl?: number | null;
  // Vom Nutzer als Favorit markiert.
  favorit?: boolean;
  // Mit mindestens einer anderen Person geteilt (Kennzeichen in der Liste).
  geteilt?: boolean;
  // Name des Eigentuemers (nur in der Geteilt-Liste gesetzt).
  besitzer_name?: string | null;
  // Bild, Audio oder Video (vom Server bestimmt), sonst null.
  medienart?: Medienart | null;
}

export type Medienart = "bild" | "audio" | "video";

export interface Pfadteil {
  id: string | null;
  name: string;
}

// Ein Eintrag der baumweiten Medienliste.
export interface Medium {
  id: string;
  name: string;
  art: Medienart;
  etag: string | null;
  groesse: number | null;
  geaendert_am: string;
  pfad: Pfadteil[];
}

export interface Konto {
  id: string;
  name: string;
}

export interface Freigabe {
  ziel_benutzer_id: string;
  ziel_name: string;
  rechte: string;
}

export interface SpeicherStatus {
  benutzt: number;
  quota: number | null;
  gesamt?: number | null;
  frei?: number | null;
  ort?: string | null;
  verfuegbar?: boolean;
}

export interface Verschiebung {
  status: string; // leer | laeuft | fertig | fehler
  kopiert: number;
  gesamt: number;
  ziel: string | null;
  fehler: string | null;
}

export interface BlobRef {
  besitzer_id: string;
  hash: string;
  groesse: number;
}

export interface PoolPruefung {
  verwaist: number;
  verwaist_bytes: number;
  fehlend: number;
  fehlend_liste: BlobRef[];
  beschaedigt: number;
  beschaedigt_liste: BlobRef[];
  geprueft: number;
}

export interface PoolAufraeumen {
  entfernt: number;
  bytes: number;
}

export interface Version {
  id: string;
  groesse: number;
  inhalt_hash: string;
  erstellt_am: string;
}

export interface AuthStatus {
  angemeldet: boolean;
  benutzer?: Benutzer | null;
}

export interface ExternEintrag {
  name: string;
  ist_ordner: boolean;
  groesse: number;
  geaendert_am: string | null;
}

export interface Vorgang {
  id: string;
  art: string; // z.B. "indizierung"
  titel: string;
  status: string; // laeuft | fertig | fehler | abgebrochen
  erledigt: number;
  gesamt: number; // 0 = unbestimmt
  fehler?: string | null;
}

// --- Zugänge für eigene Apps ----------------------------------------------------
export type Recht = "lesen" | "schreiben";

export interface AppRecht {
  knoten_id: string;
  pfad: string;
  recht: Recht;
}

export interface AppZugang {
  id: string;
  app: string;
  aktiv: boolean;
  erstellt_am: string;
  zuletzt_genutzt: string | null;
  rechte: AppRecht[];
}

export interface AppZugangNeu {
  zugang: AppZugang;
  schluessel: string;
}

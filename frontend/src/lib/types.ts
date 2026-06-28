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
  // Name des Eigentuemers (nur in der Geteilt-Liste gesetzt).
  besitzer_name?: string | null;
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

// Aktive Ansichts-App (Plugin) fuer die App-Leiste.
export interface App {
  id: string;
  name: string;
  icon: string;
  kategorie: string;
}

// Vollbild eines Plugins fuer das Admin-Panel.
export interface PluginInfo {
  id: string;
  name: string;
  version: string;
  kategorie: string;
  aktiv: boolean;
  defekt: string | null;
  quelle: string;
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

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
}

export interface SpeicherStatus {
  benutzt: number;
  quota: number | null;
  gesamt?: number | null;
  frei?: number | null;
  ort?: string | null;
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

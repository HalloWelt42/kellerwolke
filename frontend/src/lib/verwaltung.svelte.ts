// Ob die Verwaltung (Einstellungen) offen ist und welche Seite sie zeigt; eine Stelle für Kopf, Adresse und Seite.
export type EinstellungsSeite = "konten" | "speicher" | "extern" | "zugaenge" | "geraete";
export const ADMIN_SEITEN: EinstellungsSeite[] = ["konten", "speicher", "extern"];
export const EINSTELLUNGS_SEITEN: EinstellungsSeite[] = ["konten", "speicher", "extern", "zugaenge", "geraete"];

export const verwaltung = $state<{ offen: boolean; seite: EinstellungsSeite | null }>({ offen: false, seite: null });

// Die gezeigte Seite: die gewählte, wenn das Konto sie sehen darf, sonst die erste erlaubte.
export function verwaltungsSeite(istAdmin: boolean): EinstellungsSeite {
  const s = verwaltung.seite;
  if (s && (istAdmin || !ADMIN_SEITEN.includes(s))) return s;
  return istAdmin ? "konten" : "zugaenge";
}

export function verwaltungOeffnen(seite: EinstellungsSeite | null = null): void {
  verwaltung.seite = seite;
  verwaltung.offen = true;
}

export function verwaltungSchliessen(): void {
  verwaltung.offen = false;
}

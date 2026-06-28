// Reiner App-Auswahl-Zustand OHNE Plugin-Importe. Bewusst getrennt von der
// Registry (die per import.meta.glob alle Plugins laedt): so darf ein Plugin den
// App-Wechsel nutzen, ohne einen Importzyklus registry -> plugin -> registry zu
// erzeugen.

export const DEFAULT_APP_ID = "dateien";

export const appZustand = $state<{ aktivId: string; aktivierteIds: string[] }>({
  aktivId: DEFAULT_APP_ID,
  aktivierteIds: [],
});

// Eine App in der App-Leiste auswaehlen (z.B. zurueck auf "dateien").
export function waehleApp(id: string): void {
  appZustand.aktivId = id;
}

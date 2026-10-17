// Ob der Server gerade erreichbar ist. api.ts setzt den Stand bei jeder Antwort
// (erreichbar) und jedem Netzfehler (nicht erreichbar); die Oberfläche zeigt
// dann ein Band statt leerer Listen.
export const verbindung = $state<{ ok: boolean }>({ ok: true });

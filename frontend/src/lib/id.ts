// Eindeutige ID fuer interne Zwecke (Listen-Schluessel, Pane-/Filter-Identitaet).
// crypto.randomUUID gibt es NUR im sicheren Kontext (HTTPS oder localhost) -
// ueber eine LAN-IP per http ist es nicht verfuegbar. Darum ein Fallback, der
// ohne Krypto auskommt; die IDs sind reine Schluessel, keine Geheimnisse.

let zaehler = 0;

export function eindeutigeId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  zaehler += 1;
  return `id-${Date.now().toString(36)}-${zaehler}-${Math.random().toString(36).slice(2, 8)}`;
}

// Inhalt des QR-Codes eines App-Zugangs (KW-2): Adresse der Kellerwolke und App-Schlüssel als JSON,
//   {"kellerwolke": "https://192.168.178.49:39280", "schluessel": "kw_app_..."}
// Apps mit dem Appkern lesen genau dieses Format (Appkern, oberflaeche/lib/kellerwolke-qr.ts) und füllen damit die
// Einstellungen Kellerwolke und App-Schlüssel. Die Adresse ist die, unter der man die Kellerwolke gerade nutzt.
export function zugangQrText(schluessel: string): string {
  return JSON.stringify({ kellerwolke: location.origin, schluessel });
}

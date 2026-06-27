import { defineConfig } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";
import { readFileSync } from "node:fs";

// Werte aus der Projekt-.env lesen, damit Dev-Server, Proxy und Bind-Adresse je
// Klon passen (z. B. 0.0.0.0 fuer den LAN-Betrieb auf dem Pi).
function envWert(schluessel: string): string | null {
  try {
    const env = readFileSync(new URL("../.env", import.meta.url), "utf-8");
    const treffer = env.match(new RegExp(`^${schluessel}="?([^"\\n]+)"?`, "m"));
    if (treffer) return treffer[1];
  } catch {
    // Standard unten
  }
  return null;
}

function envPort(schluessel: string, standard: number): number {
  const wert = envWert(schluessel);
  return wert && /^\d+$/.test(wert) ? Number(wert) : standard;
}

export default defineConfig({
  plugins: [svelte()],
  server: {
    host: envWert("KELLERWOLKE_BIND") ?? "127.0.0.1",
    port: envPort("KELLERWOLKE_FRONTEND_PORT", 5200),
    strictPort: true,
    proxy: {
      "/api": {
        target: `http://127.0.0.1:${envPort("KELLERWOLKE_BACKEND_PORT", 8460)}`,
        changeOrigin: true,
      },
    },
  },
});

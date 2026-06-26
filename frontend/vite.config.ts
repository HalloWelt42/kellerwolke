import { defineConfig } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";
import { readFileSync } from "node:fs";

// Ports aus der Projekt-.env lesen, damit Dev-Server und Proxy je Klon passen.
function envPort(schluessel: string, standard: number): number {
  try {
    const env = readFileSync(new URL("../.env", import.meta.url), "utf-8");
    const treffer = env.match(new RegExp(`^${schluessel}="?(\\d+)"?`, "m"));
    if (treffer) return Number(treffer[1]);
  } catch {
    // Standard unten
  }
  return standard;
}

export default defineConfig({
  plugins: [svelte()],
  server: {
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

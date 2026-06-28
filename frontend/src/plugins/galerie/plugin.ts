import type { AppPlugin } from "../typen";
import Galerie from "./Galerie.svelte";

// Registrierung der Bildergalerie als Ansichts-App. Sie sitzt auf demselben
// Browser wie der Datei-Browser und ist in den Datei-Bereichen sinnvoll.
const plugin: AppPlugin = {
  id: "galerie",
  label: "Bildergalerie",
  icon: "fa-solid fa-images",
  reihenfolge: 10,
  bereiche: ["dateien", "favoriten", "geteilt"],
  ansicht: Galerie,
};

export default plugin;

import type { AppPlugin } from "../typen";
import type { Knoten } from "../../lib/types";
import Galerie from "./Galerie.svelte";
import GalerieVorschau from "./GalerieVorschau.svelte";
import GalerieVollbild from "./GalerieVollbild.svelte";
import { istBild } from "./bilder";

// Registrierung der Bildergalerie als Ansichts-App. Sie sitzt auf demselben
// Browser wie der Datei-Browser und ist in den Datei-Bereichen sinnvoll.
// Zusaetzlich verleiht sie Bild-Dateien die Faehigkeit, im Normalmodus eine
// Detail-Vorschau und eine Vollansicht zu zeigen.
const plugin: AppPlugin = {
  id: "galerie",
  label: "Bildergalerie",
  icon: "fa-solid fa-images",
  reihenfolge: 10,
  bereiche: ["dateien", "favoriten", "geteilt"],
  ansicht: Galerie,
  dateiFaehigkeiten: [
    {
      id: "bild",
      passt: (k: Knoten) => k.typ === "datei" && istBild(k.name),
      vorschau: GalerieVorschau,
      vollansicht: GalerieVollbild,
    },
  ],
};

export default plugin;

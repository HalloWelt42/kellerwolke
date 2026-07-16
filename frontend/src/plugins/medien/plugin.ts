import type { AppPlugin } from "../typen";
import type { Knoten } from "../../lib/types";
import Medien from "./Medien.svelte";
import BildVorschau from "./BildVorschau.svelte";
import BildVollbild from "./BildVollbild.svelte";
import AudioVorschau from "./AudioVorschau.svelte";
import VideoVorschau from "./VideoVorschau.svelte";
import VideoVollbild from "./VideoVollbild.svelte";
import { istBild, istAudio, istVideo } from "./medien";

// Medien-App: Bilder + Audio in einer Ansicht mit Player-Leiste. Zusaetzlich
// verleiht sie Bild- und Audio-Dateien im Normalmodus eine Detail-Faehigkeit.
const plugin: AppPlugin = {
  id: "medien",
  label: "Medien",
  icon: "fa-solid fa-photo-film",
  reihenfolge: 10,
  bereiche: ["dateien", "favoriten", "geteilt"],
  ansicht: Medien,
  dateiFaehigkeiten: [
    {
      id: "bild",
      passt: (k: Knoten) => k.typ === "datei" && istBild(k.name),
      vorschau: BildVorschau,
      vollansicht: BildVollbild,
    },
    {
      id: "audio",
      passt: (k: Knoten) => k.typ === "datei" && istAudio(k.name),
      vorschau: AudioVorschau,
    },
    {
      id: "video",
      passt: (k: Knoten) => k.typ === "datei" && istVideo(k.name),
      vorschau: VideoVorschau,
      vollansicht: VideoVollbild,
    },
  ],
};

export default plugin;

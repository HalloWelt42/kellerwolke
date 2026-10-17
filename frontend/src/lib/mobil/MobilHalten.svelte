<script lang="ts">
  import { haupt, endgueltigLoeschen } from "../zustand.svelte";
  import { mSymbol } from "./anzeige";
  import HaltenKnopf from "./HaltenKnopf.svelte";
  import { blattSchliessen, type EintragKurz } from "./mobil.svelte";

  // Bestätigung per Halten: in den Papierkorb (wiederherstellbar) oder endgültig.
  interface Props {
    knoten: EintragKurz;
    was: "loeschen" | "endgueltig";
    fertig?: () => void;
  }
  let { knoten: k, was, fertig }: Props = $props();
  const s = $derived(mSymbol(k));

  // Erst alles festhalten, dann das Blatt schließen: danach gibt es dieses Bauteil nicht mehr.
  async function ausloesen() {
    const id = k.id;
    const art = was;
    const danach = fertig;
    blattSchliessen();
    if (art === "loeschen") await haupt.loeschen([id]);
    else await endgueltigLoeschen(haupt, [id]);
    danach?.();
  }
</script>

<div class="m-blatt-kopf">
  <i class="fa-solid {s.icon} m-symbol {s.klasse}"></i>
  <div class="m-text">
    <div class="m-name">{k.name}</div>
    <div class="m-meta">
      {was === "loeschen" ? "Kommt in den Papierkorb und lässt sich dort wiederherstellen" : "Wird endgültig gelöscht und lässt sich nicht zurückholen"}
    </div>
  </div>
</div>
<HaltenKnopf text={was === "loeschen" ? "Halten zum Löschen" : "Halten zum endgültigen Löschen"} {ausloesen} />
<span class="m-leise">Loslassen bricht ab</span>

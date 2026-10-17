<script lang="ts">
  import type { Rechte } from "./browser.svelte";

  // Leiste für eine Mehrfachauswahl: bietet nur, was der Bereich erlaubt
  // (dieselbe Rechtetabelle wie Kontextmenü und Werkzeugleiste).
  interface Props {
    anzahl: number;
    rechte: Rechte;
    herunterladbar: boolean;
    onHerunterladen: () => void;
    onVerschieben: () => void;
    onLoeschen: () => void;
    onWiederherstellen: () => void;
    onEndgueltig: () => void;
    onAbbrechen: () => void;
  }
  let {
    anzahl,
    rechte,
    herunterladbar,
    onHerunterladen,
    onVerschieben,
    onLoeschen,
    onWiederherstellen,
    onEndgueltig,
    onAbbrechen,
  }: Props = $props();
</script>

<div class="auswahlleiste">
  <span class="anzahl">{anzahl}</span>
  <span>ausgewählt</span>
  <span class="trenner"></span>

  {#if rechte.wiederherstellen}
    <button onclick={onWiederherstellen}>
      <i class="fa-solid fa-rotate-left"></i> Wiederherstellen
    </button>
  {/if}
  {#if rechte.endgueltig}
    <button onclick={onEndgueltig}>
      <i class="fa-solid fa-trash"></i> Endgültig löschen
    </button>
  {/if}
  {#if herunterladbar}
    <button onclick={onHerunterladen}>
      <i class="fa-solid fa-download"></i> Herunterladen
    </button>
  {/if}
  {#if rechte.verschieben}
    <button title="In einen Ordner ziehen oder hier wählen" onclick={onVerschieben}>
      <i class="fa-solid fa-arrow-right-arrow-left"></i> Verschieben
    </button>
  {/if}
  {#if rechte.loeschen}
    <button onclick={onLoeschen}>
      <i class="fa-solid fa-trash"></i> Löschen
    </button>
  {/if}

  <span class="trenner"></span>
  <button title="Auswahl aufheben" onclick={onAbbrechen} aria-label="Auswahl aufheben">
    <i class="fa-solid fa-xmark"></i>
  </button>
</div>

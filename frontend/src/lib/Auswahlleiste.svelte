<script lang="ts">
  interface Props {
    anzahl: number;
    modus: "dateien" | "papierkorb" | "suche";
    onHerunterladen: () => void;
    onVerschieben: () => void;
    onLoeschen: () => void;
    onWiederherstellen: () => void;
    onAbbrechen: () => void;
  }
  let {
    anzahl,
    modus,
    onHerunterladen,
    onVerschieben,
    onLoeschen,
    onWiederherstellen,
    onAbbrechen,
  }: Props = $props();
</script>

<div class="auswahlleiste">
  <span class="anzahl">{anzahl}</span>
  <span>ausgewählt</span>
  <span class="trenner"></span>

  {#if modus === "papierkorb"}
    <button onclick={onWiederherstellen}>
      <i class="fa-solid fa-rotate-left"></i> Wiederherstellen
    </button>
  {:else}
    <button onclick={onHerunterladen}>
      <i class="fa-solid fa-download"></i> Herunterladen
    </button>
    {#if modus === "dateien"}
      <button title="In einen Ordner ziehen oder hier wählen" onclick={onVerschieben}>
        <i class="fa-solid fa-arrow-right-arrow-left"></i> Verschieben
      </button>
      <button onclick={onLoeschen}>
        <i class="fa-solid fa-trash"></i> Löschen
      </button>
    {/if}
  {/if}

  <span class="trenner"></span>
  <button title="Auswahl aufheben" onclick={onAbbrechen} aria-label="Auswahl aufheben">
    <i class="fa-solid fa-xmark"></i>
  </button>
</div>

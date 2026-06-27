<script lang="ts">
  import { zustand, istSchreibbar, hochladen, ladeExtern } from "./zustand.svelte";

  interface Props {
    onNeuerOrdner: () => void;
    onPapierkorbLeeren: () => void;
  }
  let { onNeuerOrdner, onPapierkorbLeeren }: Props = $props();

  function aufDateiwahl(e: Event) {
    const ziel = e.target as HTMLInputElement;
    hochladen(ziel.files);
    ziel.value = "";
  }
</script>

<div class="werkzeuge">
  {#if istSchreibbar()}
    <button class="knopf primaer" onclick={onNeuerOrdner}>
      <i class="fa-solid fa-folder-plus"></i> Neuer Ordner
    </button>
    <label class="knopf">
      <i class="fa-solid fa-arrow-up-from-bracket"></i> Hochladen
      <input type="file" multiple onchange={aufDateiwahl} hidden />
    </label>
  {:else if zustand.bereich === "extern" && zustand.externBrowse}
    <button class="knopf" onclick={ladeExtern}>
      <i class="fa-solid fa-arrows-rotate"></i> Aktualisieren
    </button>
  {:else if zustand.bereich === "papierkorb" && zustand.eintraege.length > 0}
    <button class="knopf" onclick={onPapierkorbLeeren}>
      <i class="fa-solid fa-trash-can"></i> Papierkorb leeren
    </button>
  {/if}

  <span class="luecke"></span>

  {#if zustand.bereich !== "extern" && zustand.bereich !== "geteilt"}
    <div class="werkzeug-filter">
      <i class="fa-solid fa-filter"></i>
      <input type="text" placeholder="In dieser Ansicht filtern ..." bind:value={zustand.filter} />
      {#if zustand.filter}
        <button class="icon-knopf" title="Filter löschen" aria-label="Filter löschen" onclick={() => (zustand.filter = "")} style="width: 24px; height: 24px;">
          <i class="fa-solid fa-xmark"></i>
        </button>
      {/if}
    </div>
  {/if}

  <div class="ansicht-umschalter">
    <button
      class:aktiv={zustand.ansicht === "liste"}
      title="Liste"
      onclick={() => (zustand.ansicht = "liste")}
    >
      <i class="fa-solid fa-list"></i>
    </button>
    <button
      class:aktiv={zustand.ansicht === "grid"}
      title="Kacheln"
      onclick={() => (zustand.ansicht = "grid")}
    >
      <i class="fa-solid fa-table-cells-large"></i>
    </button>
  </div>
</div>

<script lang="ts">
  import { zustand, haupt, hochladen, navUmschalten } from "./zustand.svelte";

  interface Props {
    onNeuerOrdner: () => void;
    onPapierkorbLeeren: () => void;
  }
  let { onNeuerOrdner, onPapierkorbLeeren }: Props = $props();

  // Globale Werkzeugleiste fuer die Einzelansicht (haupt). Der Filter sitzt
  // jetzt je Ansicht/Pane in der Dateiliste; im Splitscreen liegen Anlegen/
  // Hochladen je Pane.
  const istSplit = $derived(zustand.split && haupt.bereich === "dateien");

  function aufDateiwahl(e: Event) {
    const ziel = e.target as HTMLInputElement;
    hochladen(ziel.files, haupt);
    ziel.value = "";
  }
</script>

<div class="werkzeuge">
  {#if zustand.navAus}
    <button
      class="icon-knopf"
      title="Navigation einblenden"
      aria-label="Navigation einblenden"
      onclick={navUmschalten}
    >
      <i class="fa-solid fa-bars"></i>
    </button>
  {/if}

  {#if istSplit}
    <!-- Anlegen/Hochladen sitzen im Splitscreen je Pane -->
  {:else if haupt.istSchreibbar}
    <button class="knopf primaer" onclick={onNeuerOrdner}>
      <i class="fa-solid fa-folder-plus"></i> Neuer Ordner
    </button>
    <label class="knopf">
      <i class="fa-solid fa-arrow-up-from-bracket"></i> Hochladen
      <input type="file" multiple onchange={aufDateiwahl} hidden />
    </label>
  {:else if haupt.bereich === "extern" && haupt.externBrowse}
    <button class="knopf primaer" onclick={onNeuerOrdner}>
      <i class="fa-solid fa-folder-plus"></i> Neuer Ordner
    </button>
    <label class="knopf">
      <i class="fa-solid fa-arrow-up-from-bracket"></i> Hochladen
      <input type="file" multiple onchange={aufDateiwahl} hidden />
    </label>
    <button class="knopf" onclick={() => haupt.ladeExtern()}>
      <i class="fa-solid fa-arrows-rotate"></i> Aktualisieren
    </button>
  {:else if haupt.bereich === "papierkorb" && haupt.eintraege.length > 0}
    <button class="knopf" onclick={onPapierkorbLeeren}>
      <i class="fa-solid fa-trash-can"></i> Papierkorb leeren
    </button>
  {/if}

  <span class="luecke"></span>

  <div class="ansicht-umschalter">
    <button
      class:aktiv={!zustand.split && haupt.ansicht === "liste"}
      title="Liste"
      onclick={() => {
        zustand.split = false;
        haupt.ansicht = "liste";
      }}
    >
      <i class="fa-solid fa-list"></i>
    </button>
    <button
      class:aktiv={!zustand.split && haupt.ansicht === "grid"}
      title="Kacheln"
      onclick={() => {
        zustand.split = false;
        haupt.ansicht = "grid";
      }}
    >
      <i class="fa-solid fa-table-cells-large"></i>
    </button>
    <button
      class:aktiv={zustand.split}
      title="Splitscreen"
      onclick={() => (zustand.split = true)}
    >
      <i class="fa-solid fa-table-columns"></i>
    </button>
  </div>
</div>

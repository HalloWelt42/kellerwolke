<script lang="ts">
  import {
    zustand,
    zeigeDateien,
    zeigePapierkorb,
    zeigeExterneQuellen,
    zeigeFavoriten,
    zeigeGeteilt,
    navUmschalten,
  } from "./zustand.svelte";
  import Speicheranzeige from "./Speicheranzeige.svelte";

  // Linke Zone: Bereiche. Favoriten und Geteilt sind noch nicht hinterlegt und
  // daher als "bald" gekennzeichnet (kein vorgetaeuschter Inhalt).
</script>

<nav class="nav">
  <div class="nav-titel">
    Bereiche
    <button
      class="nav-einklapp"
      title="Navigation ausblenden"
      aria-label="Navigation ausblenden"
      onclick={navUmschalten}
    >
      <i class="fa-solid fa-angles-left"></i>
    </button>
  </div>

  <button class="nav-eintrag" class:aktiv={zustand.bereich === "dateien"} onclick={zeigeDateien}>
    <i class="fa-solid fa-folder"></i> Meine Dateien
  </button>

  <button class="nav-eintrag" class:aktiv={zustand.bereich === "favoriten"} onclick={zeigeFavoriten}>
    <i class="fa-solid fa-star"></i> Favoriten
  </button>

  <button class="nav-eintrag" class:aktiv={zustand.bereich === "geteilt"} onclick={zeigeGeteilt}>
    <i class="fa-solid fa-share-nodes"></i> Geteilt
  </button>

  <button
    class="nav-eintrag"
    class:aktiv={zustand.bereich === "extern"}
    onclick={zeigeExterneQuellen}
  >
    <i class="fa-solid fa-folder-tree"></i> Externe Quellen
  </button>

  <button
    class="nav-eintrag"
    class:aktiv={zustand.bereich === "papierkorb"}
    onclick={zeigePapierkorb}
  >
    <i class="fa-solid fa-trash"></i> Papierkorb
  </button>

  <div class="nav-fuss">
    <Speicheranzeige />
    {#if zustand.version}
      <div class="nav-version">Kellerwolke v{zustand.version}</div>
    {/if}
  </div>
</nav>

<style>
  .nav-version {
    margin: var(--a3) var(--a3) var(--a1);
    font-size: 0.72rem;
    color: var(--text-3);
  }
</style>

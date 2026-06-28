<script lang="ts">
  import { zustand, haupt, navUmschalten } from "./zustand.svelte";
  import Speicheranzeige from "./Speicheranzeige.svelte";

  // Linke Zone: Bereiche. Steuert die Einzelansicht (haupt).
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

  <button class="nav-eintrag" class:aktiv={haupt.bereich === "dateien"} onclick={() => haupt.zeigeDateien()}>
    <i class="fa-solid fa-folder"></i> Meine Dateien
  </button>

  <button class="nav-eintrag" class:aktiv={haupt.bereich === "favoriten"} onclick={() => haupt.zeigeFavoriten()}>
    <i class="fa-solid fa-star"></i> Favoriten
  </button>

  <button class="nav-eintrag" class:aktiv={haupt.bereich === "geteilt"} onclick={() => haupt.zeigeGeteilt()}>
    <i class="fa-solid fa-share-nodes"></i> Geteilt
  </button>

  <button class="nav-eintrag" class:aktiv={haupt.bereich === "extern"} onclick={() => haupt.zeigeExterneQuellen()}>
    <i class="fa-solid fa-folder-tree"></i> Externe Quellen
  </button>

  <button class="nav-eintrag" class:aktiv={haupt.bereich === "papierkorb"} onclick={() => haupt.zeigePapierkorb()}>
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

<script lang="ts">
  import type { Browser } from "./browser.svelte";

  // Breadcrumb einer Browsing-Instanz (Einzelansicht oder Pane). Ebenen sind
  // Ablageziele: zieht man eine Auswahl auf eine uebergeordnete Ebene, wandert
  // sie dorthin (Verschieben nach oben).
  interface Props {
    browser: Browser;
  }
  let { browser }: Props = $props();

  let zielIndex = $state<number | null>(null);

  function ueber(e: DragEvent, i: number) {
    if (!Array.from(e.dataTransfer?.types ?? []).includes("text/kellerwolke")) return;
    e.preventDefault();
    if (e.dataTransfer) e.dataTransfer.dropEffect = "move";
    zielIndex = i;
  }
  function raus(i: number) {
    if (zielIndex === i) zielIndex = null;
  }
  function fallen(e: DragEvent, zielId: string | null) {
    e.preventDefault();
    zielIndex = null;
    const roh = e.dataTransfer?.getData("text/kellerwolke");
    const ids = (roh ?? "").split(",").filter(Boolean);
    if (ids.length) browser.verschiebe(ids, zielId);
  }
</script>

{#if browser.bereich === "dateien"}
  <nav class="breadcrumb">
    {#each browser.pfad as teil, i (i)}
      {#if i > 0}<i class="fa-solid fa-chevron-right"></i>{/if}
      {#if i === browser.pfad.length - 1}
        <span class="aktuell">{teil.name}</span>
      {:else}
        <a
          class:ziel={zielIndex === i}
          ondragover={(e) => ueber(e, i)}
          ondragleave={() => raus(i)}
          ondrop={(e) => fallen(e, teil.id)}
          onclick={() => browser.breadcrumbGehe(i)}>{teil.name}</a
        >
      {/if}
    {/each}
  </nav>
{:else if browser.bereich === "extern" && browser.externBrowse}
  <nav class="breadcrumb">
    <a onclick={() => browser.externBreadcrumb(-1)}>Externe Quellen</a>
    <i class="fa-solid fa-chevron-right"></i>
    {#if browser.externBrowse.unterpfad.length === 0}
      <span class="aktuell">{browser.externBrowse.name}</span>
    {:else}
      <a onclick={() => browser.externBreadcrumb(0)}>{browser.externBrowse.name}</a>
    {/if}
    {#each browser.externBrowse.unterpfad as teil, i (i)}
      <i class="fa-solid fa-chevron-right"></i>
      {#if i === browser.externBrowse.unterpfad.length - 1}
        <span class="aktuell">{teil}</span>
      {:else}
        <a onclick={() => browser.externBreadcrumb(i + 1)}>{teil}</a>
      {/if}
    {/each}
  </nav>
{:else if browser.bereich === "extern"}
  <nav class="breadcrumb">
    <span class="aktuell">Externe Quellen</span>
  </nav>
{:else if browser.bereich === "favoriten"}
  <nav class="breadcrumb">
    <i class="fa-solid fa-star"></i> <span class="aktuell">Favoriten</span>
  </nav>
{:else if browser.bereich === "geteilt"}
  <nav class="breadcrumb">
    {#if browser.geteiltPfad.length === 0}
      <i class="fa-solid fa-share-nodes"></i> <span class="aktuell">Geteilt</span>
    {:else}
      <a onclick={() => browser.geteiltBreadcrumb(-1)}>Geteilt</a>
      {#each browser.geteiltPfad as teil, i (i)}
        <i class="fa-solid fa-chevron-right"></i>
        {#if i === browser.geteiltPfad.length - 1}
          <span class="aktuell">{teil.name}</span>
        {:else}
          <a onclick={() => browser.geteiltBreadcrumb(i)}>{teil.name}</a>
        {/if}
      {/each}
    {/if}
  </nav>
{:else if browser.bereich === "papierkorb"}
  <nav class="breadcrumb">
    <i class="fa-solid fa-trash"></i> <span class="aktuell">Papierkorb</span>
  </nav>
{:else if browser.bereich === "suche"}
  <nav class="breadcrumb">
    <i class="fa-solid fa-magnifying-glass"></i>
    <span class="aktuell">Suchergebnisse für "{browser.suchbegriff}"</span>
  </nav>
{/if}

<style>
  .breadcrumb a.ziel {
    background: var(--akzent-weich);
    color: var(--akzent-stark);
    outline: 1px dashed var(--akzent);
    outline-offset: -1px;
  }
</style>

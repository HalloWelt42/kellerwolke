<script lang="ts">
  import {
    zustand,
    breadcrumbGehe,
    externBreadcrumb,
    geteiltBreadcrumb,
    verschiebe,
  } from "./zustand.svelte";

  // Breadcrumb-Ebenen sind Ablageziele: zieht man eine Auswahl auf eine
  // uebergeordnete Ebene, wandert sie dorthin (Verschieben nach oben).
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
    if (ids.length) verschiebe(ids, zielId);
  }
</script>

{#if zustand.bereich === "dateien"}
  <nav class="breadcrumb">
    {#each zustand.pfad as teil, i (i)}
      {#if i > 0}<i class="fa-solid fa-chevron-right"></i>{/if}
      {#if i === zustand.pfad.length - 1}
        <span class="aktuell">{teil.name}</span>
      {:else}
        <a
          class:ziel={zielIndex === i}
          ondragover={(e) => ueber(e, i)}
          ondragleave={() => raus(i)}
          ondrop={(e) => fallen(e, teil.id)}
          onclick={() => breadcrumbGehe(i)}>{teil.name}</a
        >
      {/if}
    {/each}
  </nav>
{:else if zustand.bereich === "extern" && zustand.externBrowse}
  <nav class="breadcrumb">
    <a onclick={() => externBreadcrumb(-1)}>Externe Quellen</a>
    <i class="fa-solid fa-chevron-right"></i>
    {#if zustand.externBrowse.unterpfad.length === 0}
      <span class="aktuell">{zustand.externBrowse.name}</span>
    {:else}
      <a onclick={() => externBreadcrumb(0)}>{zustand.externBrowse.name}</a>
    {/if}
    {#each zustand.externBrowse.unterpfad as teil, i (i)}
      <i class="fa-solid fa-chevron-right"></i>
      {#if i === zustand.externBrowse.unterpfad.length - 1}
        <span class="aktuell">{teil}</span>
      {:else}
        <a onclick={() => externBreadcrumb(i + 1)}>{teil}</a>
      {/if}
    {/each}
    <span class="nur-lesen">nur lesen</span>
  </nav>
{:else if zustand.bereich === "extern"}
  <nav class="breadcrumb">
    <span class="aktuell">Externe Quellen</span>
  </nav>
{:else if zustand.bereich === "favoriten"}
  <nav class="breadcrumb">
    <i class="fa-solid fa-star"></i> <span class="aktuell">Favoriten</span>
  </nav>
{:else if zustand.bereich === "geteilt"}
  <nav class="breadcrumb">
    {#if zustand.geteiltPfad.length === 0}
      <i class="fa-solid fa-share-nodes"></i> <span class="aktuell">Geteilt</span>
    {:else}
      <a onclick={() => geteiltBreadcrumb(-1)}>Geteilt</a>
      {#each zustand.geteiltPfad as teil, i (i)}
        <i class="fa-solid fa-chevron-right"></i>
        {#if i === zustand.geteiltPfad.length - 1}
          <span class="aktuell">{teil.name}</span>
        {:else}
          <a onclick={() => geteiltBreadcrumb(i)}>{teil.name}</a>
        {/if}
      {/each}
    {/if}
  </nav>
{:else if zustand.bereich === "papierkorb"}
  <nav class="breadcrumb">
    <i class="fa-solid fa-trash"></i> <span class="aktuell">Papierkorb</span>
  </nav>
{:else if zustand.bereich === "suche"}
  <nav class="breadcrumb">
    <i class="fa-solid fa-magnifying-glass"></i>
    <span class="aktuell">Suchergebnisse für "{zustand.suchbegriff}"</span>
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

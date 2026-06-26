<script lang="ts">
  import { zustand, breadcrumbGehe, externBreadcrumb } from "./zustand.svelte";
</script>

{#if zustand.bereich === "dateien"}
  <nav class="breadcrumb">
    {#each zustand.pfad as teil, i (i)}
      {#if i > 0}<i class="fa-solid fa-chevron-right"></i>{/if}
      {#if i === zustand.pfad.length - 1}
        <span class="aktuell">{teil.name}</span>
      {:else}
        <a onclick={() => breadcrumbGehe(i)}>{teil.name}</a>
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

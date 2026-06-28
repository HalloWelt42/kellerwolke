<script lang="ts">
  import { sichtbareApps, appZustand, waehleApp } from "../plugins/registry.svelte";

  // Schmale Leiste unter dem Hauptsuchfeld: die aktiven Ansichts-Apps. Der
  // Datei-Browser ("Dateien") ist immer der erste Eintrag (Default-App).
  const apps = $derived(sichtbareApps());
</script>

{#if apps.length > 1}
  <div class="app-leiste">
    {#each apps as app (app.id)}
      <button
        type="button"
        class="app-knopf"
        class:aktiv={appZustand.aktivId === app.id}
        title={app.label}
        onclick={() => waehleApp(app.id)}
      >
        <i class={app.icon}></i>
        <span>{app.label}</span>
      </button>
    {/each}
  </div>
{/if}

<style>
  .app-leiste {
    display: flex;
    align-items: center;
    gap: var(--a1);
    padding: var(--a2) var(--a4) 0;
    flex-wrap: wrap;
  }
  .app-knopf {
    display: inline-flex;
    align-items: center;
    gap: var(--a2);
    padding: var(--a1) var(--a3);
    border: 1px solid transparent;
    border-radius: var(--r2);
    background: transparent;
    color: var(--text-2);
    font: inherit;
    font-size: 0.86rem;
    cursor: pointer;
  }
  .app-knopf:hover {
    background: var(--flaeche-3);
    color: var(--text-1);
  }
  .app-knopf.aktiv {
    background: var(--akzent-weich);
    color: var(--akzent-stark);
    border-color: var(--akzent-rand, transparent);
  }
</style>

<script lang="ts">
  import { ansicht, waehleAnsicht, MEDIEN_BEREICHE, type HauptAnsicht } from "./ansicht.svelte";
  import { haupt } from "./zustand.svelte";

  // Schmale Leiste unter dem Kopf: Dateien oder Medien. Die Medienansicht gibt es
  // dort, wo Medien liegen können; anderswo ist ihr Knopf gesperrt und sagt warum.
  const eintraege: { id: HauptAnsicht; label: string; icon: string }[] = [
    { id: "dateien", label: "Dateien", icon: "fa-solid fa-folder" },
    { id: "medien", label: "Medien", icon: "fa-solid fa-photo-film" },
  ];
  const medienMoeglich = $derived(MEDIEN_BEREICHE.includes(haupt.bereich));
</script>

<div class="app-leiste">
  {#each eintraege as e (e.id)}
    {@const gesperrt = e.id === "medien" && !medienMoeglich}
    <button
      type="button"
      class="app-knopf"
      class:aktiv={ansicht.aktiv === e.id}
      disabled={gesperrt}
      title={gesperrt ? "Medien gibt es in Meine Dateien, Favoriten und Geteilt" : e.label}
      onclick={() => waehleAnsicht(e.id)}
    >
      <i class={e.icon}></i>
      <span>{e.label}</span>
    </button>
  {/each}
</div>

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
  .app-knopf:disabled {
    opacity: 0.45;
    cursor: not-allowed;
    background: transparent;
  }
  .app-knopf.aktiv {
    background: var(--akzent-weich);
    color: var(--akzent-stark);
    border-color: var(--akzent-rand, transparent);
  }
</style>

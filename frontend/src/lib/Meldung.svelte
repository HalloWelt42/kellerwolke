<script lang="ts">
  import type { Browser } from "./browser.svelte";

  // Fehlermeldung einer Fläche: bleibt stehen, bis man sie schliesst oder den Ort wechselt.
  interface Props {
    browser: Browser;
  }
  let { browser }: Props = $props();
</script>

{#if browser.fehler}
  <div class="fehlerstreifen meldung" role="alert">
    <span>{browser.fehler}</span>
    <button class="meldung-zu" title="Schließen" aria-label="Meldung schließen" onclick={() => browser.fehlerSchliessen()}>
      <i class="fa-solid fa-xmark"></i>
    </button>
  </div>
{/if}

<style>
  .meldung {
    display: flex;
    align-items: flex-start;
    gap: var(--a2);
  }
  .meldung span {
    flex: 1;
    min-width: 0;
    overflow-wrap: anywhere;
  }
  .meldung-zu {
    border: none;
    background: transparent;
    color: inherit;
    cursor: pointer;
    padding: 0 var(--a1);
    font-size: 0.9rem;
  }
</style>

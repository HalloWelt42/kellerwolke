<script lang="ts">
  import type { Browser } from "./browser.svelte";
  import { ARTEN } from "./ansicht.svelte";

  // Filter nach Art einer Fläche (KW-5): Knopfleiste mit Symbol, Farbe der Art und Anzahl; der Text steht im Hover.
  // Die Art wählt Inhalt und Darstellung (siehe ansicht.svelte.ts); Ordner bleiben immer sichtbar.
  interface Props {
    browser: Browser;
  }
  let { browser }: Props = $props();
</script>

<div class="seg art-wahl" role="radiogroup" aria-label="Filter nach Art">
  {#each ARTEN as a (a.id)}
    {@const zahl = browser.artZahlen[a.id]}
    <button
      type="button"
      role="radio"
      aria-checked={browser.art === a.id}
      class="art-{a.id}"
      class:aktiv={browser.art === a.id}
      disabled={a.id !== "alle" && zahl === 0 && browser.art !== a.id}
      title="{a.titel} ({zahl})"
      onclick={() => (browser.art = a.id)}
    >
      <i class={a.icon}></i>
      <span class="zahl">{zahl}</span>
    </button>
  {/each}
</div>

<style>
  .art-bild i {
    color: var(--art-bild);
  }
  .art-audio i {
    color: var(--art-audio);
  }
  .art-video i {
    color: var(--art-video);
  }
</style>

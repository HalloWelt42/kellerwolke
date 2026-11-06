<script lang="ts">
  import type { Browser } from "../browser.svelte";
  import { ARTEN } from "../ansicht.svelte";

  // Filter nach Art am Telefon (KW-5, Entwurf mockups/mobil.html): dieselben Arten wie am Rechner, als Segment mit
  // Symbol in der Farbe der Art und Anzahl. Ohne Zeiger gibt es kein Hover; die Beschriftung trägt aria-label.
  interface Props {
    browser: Browser;
  }
  let { browser }: Props = $props();
  const NAMEN: Record<string, string> = { alle: "Alles", bild: "Bilder", audio: "Ton", video: "Video" };
</script>

<div class="m-segment m-arten" role="radiogroup" aria-label="Filter nach Art">
  {#each ARTEN as a (a.id)}
    {@const zahl = browser.artZahlen[a.id]}
    <button
      type="button"
      role="radio"
      aria-checked={browser.art === a.id}
      aria-label="{NAMEN[a.id]}: {zahl}"
      class="art-{a.id}"
      class:an={browser.art === a.id}
      disabled={a.id !== "alle" && zahl === 0 && browser.art !== a.id}
      onclick={() => (browser.art = a.id)}
    >
      <i class={a.icon}></i>
      {zahl}
    </button>
  {/each}
</div>

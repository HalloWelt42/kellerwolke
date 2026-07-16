<script lang="ts">
  import type { Browser } from "../../lib/browser.svelte";
  import type { Knoten } from "../../lib/types";
  import { formatKuerzel } from "./medien";
  import { oeffneVollansicht } from "../../lib/vorschau.svelte";

  // Reine Cover-Kachel wie bei Audio: fuellt ihren Rahmen und funktioniert
  // dadurch gleich im kleinen Raster wie im Detail-Pane. Abgespielt wird in der
  // zentralen Vollansicht des Kerns, nicht hier im Kleinformat.
  interface Props { knoten: Knoten; browser: Browser; }
  let { knoten }: Props = $props();
</script>

<button
  class="vv-cover"
  onclick={() => oeffneVollansicht(knoten)}
  aria-label="Abspielen"
  title="Abspielen"
>
  <span class="vv-format">{formatKuerzel(knoten.name)}</span>
  <i class="vv-film fa-solid fa-film"></i>
  <span class="vv-play"><i class="fa-solid fa-play"></i></span>
</button>

<style>
  .vv-cover {
    width: 100%; height: 100%; border: none; padding: 0; position: relative;
    display: grid; place-items: center; color: #fff; font-size: 2.2rem;
    border-radius: inherit; overflow: hidden; cursor: pointer;
    background: linear-gradient(135deg, #1f2937, #0f766e);
  }
  .vv-film { opacity: 0.9; }
  .vv-format {
    position: absolute; top: 8px; right: 8px; font-size: 0.6rem; font-weight: 600;
    padding: 2px 7px; border-radius: 999px; background: rgba(0, 0, 0, 0.42); color: #fff;
  }
  .vv-play {
    position: absolute; inset: 0; display: grid; place-items: center;
    font-size: 1.5rem; background: rgba(0, 0, 0, 0.26);
    opacity: 0; transition: opacity 0.15s ease;
  }
  .vv-cover:hover .vv-play { opacity: 1; }
</style>

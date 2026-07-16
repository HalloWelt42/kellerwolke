<script lang="ts">
  import type { Browser } from "../../lib/browser.svelte";
  import type { Knoten } from "../../lib/types";
  import { formatKuerzel } from "./medien";

  // Passive Cover-Kachel, genau wie die Bild-Vorschau: sie ZEIGT nur.
  //
  // Das Oeffnen der Vollansicht ist Sache des Kerns (Doppelklick in der Liste,
  // Klick auf die Vorschauflaeche im Detail-Pane). Ein eigener Knopf mit
  // eigenem Oeffnen sass im Detail-Pane in einem Knopf und liess die Vollansicht
  // an zwei Stellen gleichzeitig aufgehen - das Video lief dann doppelt.
  interface Props { knoten: Knoten; browser?: Browser; }
  let { knoten }: Props = $props();
</script>

<div class="vv-cover">
  <span class="vv-format">{formatKuerzel(knoten.name)}</span>
  <i class="vv-film fa-solid fa-film"></i>
  <span class="vv-play"><i class="fa-solid fa-play"></i></span>
</div>

<style>
  .vv-cover {
    width: 100%; height: 100%; position: relative;
    display: grid; place-items: center; color: #fff; font-size: 2.2rem;
    border-radius: inherit; overflow: hidden;
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
  /* Zeigt sich, sobald die umgebende Kachel oder Vorschauflaeche beruehrt wird. */
  :global(.kachel:hover) .vv-play,
  :global(.vorschau-flaeche:hover) .vv-play {
    opacity: 1;
  }
</style>

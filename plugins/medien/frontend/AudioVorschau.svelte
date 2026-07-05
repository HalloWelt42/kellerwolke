<script lang="ts">
  import type { Browser } from "../../lib/browser.svelte";
  import type { Knoten } from "../../lib/types";
  import { player, spielen, aktuelleSpur } from "../../lib/player.svelte";
  import { streamUrl, formatKuerzel } from "./medien";
  interface Props { knoten: Knoten; browser: Browser; }
  let { knoten }: Props = $props();

  // Reine Cover-Kachel, die ihren Rahmen ausfuellt - funktioniert gleich im
  // kleinen Raster-Kachel wie im groesseren Detail-Pane. Die Wiedergabe laeuft
  // in der globalen Player-Leiste am unteren Rand (dort steht der Status), hier
  // nur Cover + Abspielsymbol.
  const aktiv = $derived(aktuelleSpur()?.id === knoten.id);
  function abspielen() {
    spielen([{ id: knoten.id, url: streamUrl(knoten.id), titel: knoten.name, pfad: null }], 0);
  }
</script>

<button
  class="av-cover"
  class:aktiv
  onclick={abspielen}
  aria-label="Abspielen"
  title={aktiv ? (player.laeuft ? "Läuft in der Leiste unten" : "Pausiert in der Leiste unten") : "Abspielen - läuft in der Leiste unten"}
>
  <span class="av-format">{formatKuerzel(knoten.name)}</span>
  <i class="av-note fa-solid fa-music"></i>
  <span class="av-play"><i class="fa-solid {aktiv && player.laeuft ? 'fa-pause' : 'fa-play'}"></i></span>
</button>

<style>
  .av-cover {
    width: 100%; height: 100%; border: none; padding: 0; position: relative;
    display: grid; place-items: center; color: #fff; font-size: 2.2rem;
    border-radius: inherit; overflow: hidden; cursor: pointer;
    background: linear-gradient(135deg, #6d5efc, #3b82f6);
  }
  .av-note { opacity: 0.92; }
  .av-format { position: absolute; top: 8px; right: 8px; font-size: 0.6rem; font-weight: 600; padding: 2px 7px; border-radius: 999px; background: rgba(0,0,0,0.42); color: #fff; }
  .av-play { position: absolute; inset: 0; display: grid; place-items: center; font-size: 1.5rem; background: rgba(0,0,0,0.26); opacity: 0; transition: opacity 0.15s ease; }
  .av-cover:hover .av-play, .av-cover.aktiv .av-play { opacity: 1; }
</style>

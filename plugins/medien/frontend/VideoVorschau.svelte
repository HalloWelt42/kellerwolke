<script lang="ts">
  import type { Browser } from "../../lib/browser.svelte";
  import type { Knoten } from "../../lib/types";
  import { formatKuerzel, thumbUrl } from "./medien";

  // Passive Cover-Kachel, genau wie die Bild-Vorschau: sie ZEIGT nur.
  //
  // Das Oeffnen der Vollansicht ist Sache des Kerns (Doppelklick in der Liste,
  // Klick auf die Vorschauflaeche im Detail-Pane). Ein eigener Knopf mit eigenem
  // Oeffnen sass im Detail-Pane in einem Knopf und liess die Vollansicht an zwei
  // Stellen gleichzeitig aufgehen - das Video lief dann doppelt.
  interface Props { knoten: Knoten; browser?: Browser; }
  let { knoten }: Props = $props();

  // Standbild aus dem Video (ffmpeg, serverseitig gecacht). Fehlt ffmpeg oder
  // mag es das Format nicht, antwortet der Server mit einem Fehler - dann bleibt
  // es beim Film-Symbol, statt eine kaputte Grafik zu zeigen.
  let kaputt = $state(false);
  $effect(() => {
    void knoten.id;
    kaputt = false;
  });
</script>

<div class="vv-cover" class:ohne-bild={kaputt}>
  {#if kaputt}
    <i class="vv-film fa-solid fa-film"></i>
  {:else}
    <img
      class="vv-bild"
      src={thumbUrl(knoten.id, 480)}
      alt={knoten.name}
      loading="lazy"
      onerror={() => (kaputt = true)}
    />
  {/if}
  <span class="vv-format">{formatKuerzel(knoten.name)}</span>
  <!-- Dauerhaft sichtbar: so ist auf einen Blick klar, dass es ein Video ist
       und kein Bild - das Standbild allein sieht sonst wie ein Foto aus. -->
  <span class="vv-play"><i class="fa-solid fa-play"></i></span>
</div>

<style>
  .vv-cover {
    width: 100%; height: 100%; position: relative;
    display: grid; place-items: center; color: #fff;
    border-radius: inherit; overflow: hidden;
    background: #000;
  }
  .vv-cover.ohne-bild {
    background: linear-gradient(135deg, #1f2937, #0f766e);
    font-size: 2.2rem;
  }
  .vv-bild { width: 100%; height: 100%; object-fit: cover; display: block; }
  .vv-film { opacity: 0.9; }
  .vv-format {
    position: absolute; top: 8px; right: 8px; font-size: 0.6rem; font-weight: 600;
    padding: 2px 7px; border-radius: 999px; background: rgba(0, 0, 0, 0.55); color: #fff;
  }
  .vv-play {
    position: absolute;
    width: 42px; height: 42px; border-radius: 50%;
    display: grid; place-items: center;
    font-size: 0.95rem;
    background: rgba(0, 0, 0, 0.5);
    border: 2px solid rgba(255, 255, 255, 0.85);
    transition: background 0.15s ease, transform 0.15s ease;
  }
  .vv-play i { margin-left: 2px; } /* optischer Ausgleich des Dreiecks */
  :global(.kachel:hover) .vv-play,
  :global(.vorschau-flaeche:hover) .vv-play {
    background: rgba(0, 0, 0, 0.75);
    transform: scale(1.08);
  }
</style>

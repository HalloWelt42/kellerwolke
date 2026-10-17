<script lang="ts">
  import { player, aktuelleSpur } from "../player.svelte";
  import { formatKuerzel } from "./adressen";

  // Cover-Kachel für Audio, die ihren Rahmen füllt (Raster wie Detail). Der
  // Knopf startet oder pausiert - und nur das: der Klick geht nicht weiter an
  // die Kachel (die sonst zusätzlich das Detail öffnen würde).
  interface Props {
    m: { id: string; name: string };
    spielen: () => void;
  }
  let { m, spielen }: Props = $props();

  const aktiv = $derived(aktuelleSpur()?.id === m.id);
</script>

<button
  class="av-cover"
  class:aktiv
  onclick={(e) => {
    e.stopPropagation();
    spielen();
  }}
  ondblclick={(e) => e.stopPropagation()}
  aria-label={aktiv && player.laeuft ? "Pause" : "Abspielen"}
  title={aktiv ? (player.laeuft ? "Läuft in der Leiste unten - klicken pausiert" : "Pausiert - klicken spielt weiter") : "Abspielen - läuft in der Leiste unten"}
>
  <span class="av-format">{formatKuerzel(m.name)}</span>
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

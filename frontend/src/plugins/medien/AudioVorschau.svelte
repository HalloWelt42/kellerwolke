<script lang="ts">
  import type { Browser } from "../../lib/browser.svelte";
  import type { Knoten } from "../../lib/types";
  import { player, spielen, aktuelleSpur } from "../../lib/player.svelte";
  import { streamUrl, formatKuerzel } from "./medien";
  interface Props { knoten: Knoten; browser: Browser; }
  let { knoten }: Props = $props();

  // Wiedergabe laeuft in der globalen Player-Leiste am unteren Rand - kein
  // natives Steuerelement hier, nur eine anklickbare Cover-Kachel.
  const aktiv = $derived(aktuelleSpur()?.id === knoten.id);
  function abspielen() {
    spielen([{ id: knoten.id, url: streamUrl(knoten.id), titel: knoten.name, pfad: null }], 0);
  }
</script>

<div class="av">
  <button class="av-cover" class:aktiv onclick={abspielen} aria-label="Abspielen">
    <span class="av-format">{formatKuerzel(knoten.name)}</span>
    <i class="av-note fa-solid fa-music"></i>
    <span class="av-play"><i class="fa-solid {aktiv && player.laeuft ? 'fa-pause' : 'fa-play'}"></i></span>
  </button>
  <div class="av-hinweis">
    {#if aktiv}
      <i class="fa-solid fa-volume-high"></i> {player.laeuft ? "Läuft in der Leiste unten" : "Pausiert in der Leiste unten"}
    {:else}
      <i class="fa-solid fa-play"></i> Klicken - spielt in der Leiste unten
    {/if}
  </div>
</div>

<style>
  .av { width: 100%; height: 100%; display: flex; flex-direction: column; gap: var(--a2); }
  .av-cover {
    flex: 1; width: 100%; border: none; padding: 0; position: relative;
    display: grid; place-items: center; color: #fff; font-size: 2.4rem;
    border-radius: var(--r2); overflow: hidden; cursor: pointer;
    background: linear-gradient(135deg, #6d5efc, #3b82f6);
  }
  .av-note { opacity: 0.92; }
  .av-format { position: absolute; top: 8px; right: 8px; font-size: 0.6rem; font-weight: 600; padding: 2px 7px; border-radius: 999px; background: rgba(0,0,0,0.42); color: #fff; }
  .av-play { position: absolute; inset: 0; display: grid; place-items: center; font-size: 1.5rem; background: rgba(0,0,0,0.26); opacity: 0; transition: opacity 0.15s ease; }
  .av-cover:hover .av-play, .av-cover.aktiv .av-play { opacity: 1; }
  .av-hinweis { display: flex; align-items: center; justify-content: center; gap: var(--a1); font-size: 0.76rem; color: var(--text-3); }
</style>

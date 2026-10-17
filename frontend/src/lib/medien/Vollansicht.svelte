<script lang="ts">
  import { untrack } from "svelte";
  import { vollansicht, aktuellesVoll, schliesseVollansicht, vollBlaettern } from "../vorschau.svelte";
  import { player, umschalten } from "../player.svelte";
  import { ursache, vollUrl, stromUrl } from "./adressen";
  import { zumOrdner } from "./oeffnen";

  // Die eine Vollansicht im Kern: Bilder mit Blättern und Diashow, Videos mit
  // den Bedienelementen des Browsers. Solange sie offen ist, hat sie bei den
  // Tasten Vorrang (Dateiliste und Player-Leiste ruhen).
  const m = $derived(aktuellesVoll());
  const anzahl = $derived(vollansicht.liste.length);
  let fehler = $state("");

  $effect(() => {
    void m?.id;
    fehler = "";
  });

  // Ein Video öffnen pausiert laufendes Audio - einmal beim Öffnen, nicht bei jedem Start danach.
  $effect(() => {
    if (m?.art !== "video") return;
    void m.id;
    untrack(() => {
      if (player.laeuft) umschalten();
    });
  });

  // Diashow: solange sie läuft und ein Bild offen ist, weiter (Videos werden übersprungen).
  $effect(() => {
    if (!vollansicht.diashow || m?.art !== "bild" || anzahl < 2) return;
    const id = setInterval(() => vollBlaettern(1, true), Math.max(1, vollansicht.intervall) * 1000);
    return () => clearInterval(id);
  });

  async function nichtGeladen(url: string) {
    fehler = await ursache(url);
  }

  function zumOrdnerGehen() {
    if (!m?.pfad) return;
    const ziel = m;
    schliesseVollansicht();
    zumOrdner(ziel.pfad as NonNullable<typeof ziel.pfad>, ziel.id);
  }

  function taste(e: KeyboardEvent) {
    if (!m) return;
    if ((e.target as HTMLElement)?.closest?.("input, textarea, select")) return;
    if (e.key === "Escape") {
      e.preventDefault();
      schliesseVollansicht();
    } else if (e.key === "ArrowRight") {
      vollBlaettern(1);
    } else if (e.key === "ArrowLeft") {
      vollBlaettern(-1);
    } else if (e.key === " " && m.art === "bild") {
      e.preventDefault();
      vollansicht.diashow = !vollansicht.diashow;
    }
  }
</script>

<svelte:window onkeydown={taste} />

{#if m}
  <div class="m-voll" role="presentation" onclick={schliesseVollansicht}>
    {#if fehler}
      <div class="m-fehler" role="presentation" onclick={(e) => e.stopPropagation()}>
        <i class="fa-solid fa-triangle-exclamation"></i>
        <span>{fehler}</span>
      </div>
    {:else if m.art === "video"}
      <!-- svelte-ignore a11y_media_has_caption -->
      <video
        class="m-voll-bild m-video"
        src={stromUrl(m)}
        controls
        autoplay
        playsinline
        onerror={() => nichtGeladen(stromUrl(m as NonNullable<typeof m>))}
        onclick={(e) => e.stopPropagation()}
      ></video>
    {:else}
      <img
        class="m-voll-bild"
        src={vollUrl(m)}
        alt={m.name}
        role="presentation"
        onerror={() => nichtGeladen(vollUrl(m as NonNullable<typeof m>))}
        onclick={(e) => e.stopPropagation()}
      />
    {/if}
    <div class="m-voll-leiste" role="presentation" onclick={(e) => e.stopPropagation()}>
      {#if anzahl > 1}
        <button class="vk" aria-label="Zurück" title="Zurück (Pfeil links)" onclick={() => vollBlaettern(-1)}><i class="fa-solid fa-chevron-left"></i></button>
      {/if}
      <span class="name" title={m.name}>{m.name}</span>
      {#if anzahl > 1}
        <span class="zaehler">{vollansicht.index + 1} / {anzahl}</span>
      {/if}
      {#if m.art === "bild" && anzahl > 1}
        <button class="vk" class:aktiv={vollansicht.diashow} title={vollansicht.diashow ? "Diashow anhalten (Leertaste)" : "Diashow (Leertaste)"} aria-label="Diashow" onclick={() => (vollansicht.diashow = !vollansicht.diashow)}><i class="fa-solid {vollansicht.diashow ? 'fa-pause' : 'fa-play'}"></i></button>
        <label class="sek" title="Sekunden je Bild"><input type="number" min="1" max="60" bind:value={vollansicht.intervall} /> s</label>
      {/if}
      {#if anzahl > 1}
        <button class="vk" aria-label="Weiter" title="Weiter (Pfeil rechts)" onclick={() => vollBlaettern(1)}><i class="fa-solid fa-chevron-right"></i></button>
      {/if}
      {#if m.pfad}
        <button class="vk" title="Zum Ordner" aria-label="Zum Ordner" onclick={zumOrdnerGehen}><i class="fa-solid fa-folder-open"></i></button>
      {/if}
      <button class="vk" aria-label="Schließen" title="Schließen (Escape)" onclick={schliesseVollansicht}><i class="fa-solid fa-xmark"></i></button>
    </div>
  </div>
{/if}

<style>
  .m-voll { position: fixed; inset: 0; background: rgba(0,0,0,0.92); display: flex; align-items: center; justify-content: center; z-index: 70; }
  .m-voll-bild { max-width: 96vw; max-height: 84vh; object-fit: contain; }
  .m-video { background: #000; outline: none; }
  .m-voll-leiste { position: absolute; bottom: calc(84px + var(--a3)); left: 50%; transform: translateX(-50%); display: flex; align-items: center; gap: var(--a2); background: rgba(20,20,24,0.9); border: 1px solid rgba(255,255,255,0.12); border-radius: var(--r3); padding: var(--a2) var(--a3); color: #fff; max-width: 94vw; }
  .m-voll-leiste .name { max-width: 30vw; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 0.86rem; }
  .m-voll-leiste .zaehler { color: rgba(255,255,255,0.6); font-size: 0.82rem; }
  .vk { border: none; background: transparent; color: #fff; cursor: pointer; font-size: 1rem; width: 32px; height: 32px; border-radius: var(--r1); flex: none; }
  .vk:hover { background: rgba(255,255,255,0.14); }
  .vk.aktiv { color: var(--akzent); }
  .sek { display: inline-flex; align-items: center; gap: 4px; font-size: 0.82rem; color: rgba(255,255,255,0.7); }
  .sek input { width: 42px; background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.15); color: #fff; border-radius: var(--r1); padding: 2px 4px; font: inherit; font-size: 0.82rem; }
  .m-fehler { display: flex; flex-direction: column; align-items: center; gap: var(--a2); color: #fff; font-size: 0.95rem; text-align: center; max-width: 420px; padding: var(--a4); }
  .m-fehler i { font-size: 2rem; color: #fbbf24; }
</style>

<script lang="ts">
  import { SvelteSet } from "svelte/reactivity";
  import type { Browser } from "../../lib/browser.svelte";
  import type { Knoten } from "../../lib/types";
  import { groesseText, symbol } from "../../lib/format";
  import { istBild, thumbUrl, inlineUrl } from "./bilder";

  interface Props {
    browser: Browser;
  }
  let { browser }: Props = $props();

  // Bilder, deren Thumbnail/Vollbild der Server nicht darstellen kann (z.B.
  // beschaedigt) - dann ein Platzhalter statt kaputtem Bild-Symbol.
  const kaputt = new SvelteSet<string>();

  type Modus = "kachel_gross" | "kachel_klein" | "liste";
  let modus = $state<Modus>("kachel_gross");
  let vollIndex = $state<number | null>(null);
  let autoplay = $state(false);
  let intervall = $state(4);

  const ordner = $derived(browser.eintraege.filter((k) => k.typ === "ordner" || k.typ === "extern"));
  const bilder = $derived(browser.eintraege.filter((k) => k.typ === "datei" && istBild(k.name)));
  const thumbKante = $derived(modus === "kachel_klein" ? 200 : modus === "liste" ? 96 : 400);

  function oeffne(k: Knoten) {
    browser.oeffnen(k);
  }
  function zeigeVoll(i: number) {
    vollIndex = i;
  }
  function schliesse() {
    vollIndex = null;
    autoplay = false;
  }
  function weiter() {
    if (vollIndex === null || bilder.length === 0) return;
    vollIndex = (vollIndex + 1) % bilder.length;
  }
  function zurueck() {
    if (vollIndex === null || bilder.length === 0) return;
    vollIndex = (vollIndex - 1 + bilder.length) % bilder.length;
  }

  function taste(e: KeyboardEvent) {
    if (vollIndex === null) return;
    if (e.key === "Escape") schliesse();
    else if (e.key === "ArrowRight") weiter();
    else if (e.key === "ArrowLeft") zurueck();
    else if (e.key === " ") {
      e.preventDefault();
      autoplay = !autoplay;
    }
  }

  // Diashow: solange autoplay laeuft und ein Bild offen ist, automatisch weiter.
  $effect(() => {
    if (autoplay && vollIndex !== null && bilder.length > 1) {
      const id = setInterval(weiter, Math.max(1, intervall) * 1000);
      return () => clearInterval(id);
    }
  });
</script>

<svelte:window onkeydown={taste} />

<div class="galerie-werkzeuge">
  <div class="modi">
    <button class="g-knopf" class:aktiv={modus === "kachel_gross"} title="Große Kacheln" onclick={() => (modus = "kachel_gross")}>
      <i class="fa-solid fa-table-cells-large"></i>
    </button>
    <button class="g-knopf" class:aktiv={modus === "kachel_klein"} title="Kleine Kacheln" onclick={() => (modus = "kachel_klein")}>
      <i class="fa-solid fa-table-cells"></i>
    </button>
    <button class="g-knopf" class:aktiv={modus === "liste"} title="Liste" onclick={() => (modus = "liste")}>
      <i class="fa-solid fa-list"></i>
    </button>
  </div>
  {#if bilder.length > 0}
    <button class="g-knopf start" title="Diashow starten" onclick={() => { vollIndex = 0; autoplay = true; }}>
      <i class="fa-solid fa-play"></i> Diashow
    </button>
    <span class="anzahl">{bilder.length} {bilder.length === 1 ? "Bild" : "Bilder"}</span>
  {/if}
</div>

{#if browser.laden}
  <div class="g-leer"><i class="fa-solid fa-circle-notch fa-spin"></i></div>
{:else if ordner.length === 0 && bilder.length === 0}
  <div class="g-leer">
    <i class="fa-regular fa-image"></i><span>Hier sind keine Bilder</span>
  </div>
{:else if modus === "liste"}
  <div class="g-liste">
    {#each ordner as k (k.id)}
      <button class="g-zeile" ondblclick={() => oeffne(k)} onclick={() => oeffne(k)}>
        <i class="sym fa-solid {symbol(k).icon} {symbol(k).klasse}"></i>
        <span class="titel">{k.name}</span>
      </button>
    {/each}
    {#each bilder as k, i (k.id)}
      <button class="g-zeile" onclick={() => zeigeVoll(i)}>
        {#if kaputt.has(k.id)}
          <span class="sym fa-regular fa-image"></span>
        {:else}
          <img src={thumbUrl(k.id, 96)} alt={k.name} loading="lazy" onerror={() => kaputt.add(k.id)} />
        {/if}
        <span class="titel">{k.name}</span>
        <span class="meta">{k.groesse != null ? groesseText(k.groesse) : ""}</span>
      </button>
    {/each}
  </div>
{:else}
  <div class="g-gitter" class:klein={modus === "kachel_klein"}>
    {#each ordner as k (k.id)}
      <button class="g-ordner" ondblclick={() => oeffne(k)} onclick={() => oeffne(k)} title={k.name}>
        <i class="fa-solid {symbol(k).icon}"></i>
        <span class="titel">{k.name}</span>
      </button>
    {/each}
    {#each bilder as k, i (k.id)}
      <button class="g-kachel" onclick={() => zeigeVoll(i)} title={k.name}>
        {#if kaputt.has(k.id)}
          <div class="g-platzhalter"><i class="fa-regular fa-image"></i></div>
        {:else}
          <img src={thumbUrl(k.id, thumbKante)} alt={k.name} loading="lazy" onerror={() => kaputt.add(k.id)} />
        {/if}
      </button>
    {/each}
  </div>
{/if}

{#if vollIndex !== null && bilder[vollIndex]}
  <div class="g-voll" role="presentation" onclick={schliesse}>
    <img
      class="g-voll-bild"
      src={inlineUrl(bilder[vollIndex].id)}
      alt={bilder[vollIndex].name}
      role="presentation"
      onclick={(e) => e.stopPropagation()}
    />
    <div class="g-voll-leiste" role="presentation" onclick={(e) => e.stopPropagation()}>
      <button class="vk" title="Zurück" aria-label="Zurück" onclick={zurueck}><i class="fa-solid fa-chevron-left"></i></button>
      <span class="name">{bilder[vollIndex].name}</span>
      <span class="zaehler">{vollIndex + 1} / {bilder.length}</span>
      <button class="vk" class:aktiv={autoplay} title={autoplay ? "Pause" : "Diashow"} aria-label="Diashow" onclick={() => (autoplay = !autoplay)}>
        <i class="fa-solid {autoplay ? 'fa-pause' : 'fa-play'}"></i>
      </button>
      <label class="sek" title="Sekunden je Bild">
        <input type="number" min="1" max="60" bind:value={intervall} /> s
      </label>
      <button class="vk" title="Weiter" aria-label="Weiter" onclick={weiter}><i class="fa-solid fa-chevron-right"></i></button>
      <button class="vk" title="Schließen" aria-label="Schließen" onclick={schliesse}><i class="fa-solid fa-xmark"></i></button>
    </div>
  </div>
{/if}

<style>
  .galerie-werkzeuge {
    display: flex;
    align-items: center;
    gap: var(--a2);
    padding: var(--a2) var(--a4);
  }
  .modi {
    display: inline-flex;
    gap: 2px;
    background: var(--flaeche-2);
    border: 1px solid var(--rand);
    border-radius: var(--r2);
    padding: 2px;
  }
  .g-knopf {
    border: none;
    background: transparent;
    color: var(--text-2);
    font: inherit;
    font-size: 0.86rem;
    padding: var(--a1) var(--a2);
    border-radius: var(--r1);
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: var(--a1);
  }
  .g-knopf:hover {
    background: var(--flaeche-3);
  }
  .g-knopf.aktiv {
    background: var(--akzent-weich);
    color: var(--akzent-stark);
  }
  .g-knopf.start {
    border: 1px solid var(--rand);
  }
  .anzahl {
    margin-left: auto;
    color: var(--text-3);
    font-size: 0.82rem;
  }
  .g-leer {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: var(--a2);
    padding: var(--a5) 0;
    color: var(--text-3);
    font-size: 1.4rem;
  }
  .g-leer span {
    font-size: 0.9rem;
  }
  .g-gitter {
    flex: 1;
    overflow-y: auto;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: var(--a3);
    padding: var(--a3) var(--a4);
    align-content: start;
  }
  .g-gitter.klein {
    grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
    gap: var(--a2);
  }
  .g-kachel {
    border: none;
    padding: 0;
    background: var(--flaeche-2);
    border-radius: var(--r2);
    overflow: hidden;
    cursor: pointer;
    aspect-ratio: 1;
  }
  .g-kachel img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
  }
  .g-platzhalter {
    width: 100%;
    height: 100%;
    display: grid;
    place-items: center;
    color: var(--text-3);
    font-size: 1.8rem;
  }
  .g-ordner {
    border: 1px solid var(--rand);
    background: var(--flaeche-2);
    border-radius: var(--r2);
    cursor: pointer;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: var(--a2);
    aspect-ratio: 1;
    color: var(--akzent);
    font-size: 2rem;
  }
  .g-ordner .titel {
    font-size: 0.8rem;
    color: var(--text-1);
    max-width: 90%;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .g-liste {
    flex: 1;
    overflow-y: auto;
    padding: 0 var(--a4) var(--a3);
  }
  .g-zeile {
    width: 100%;
    display: flex;
    align-items: center;
    gap: var(--a3);
    padding: var(--a1) var(--a2);
    border: none;
    background: transparent;
    cursor: pointer;
    text-align: left;
    color: var(--text-1);
    font: inherit;
    border-radius: var(--r1);
  }
  .g-zeile:hover {
    background: var(--flaeche-2);
  }
  .g-zeile img {
    width: 48px;
    height: 48px;
    object-fit: cover;
    border-radius: var(--r1);
    flex: none;
  }
  .g-zeile .sym {
    width: 48px;
    text-align: center;
    color: var(--akzent);
  }
  .g-zeile .titel {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .g-zeile .meta {
    color: var(--text-3);
    font-size: 0.82rem;
  }
  .g-voll {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.92);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 60;
  }
  .g-voll-bild {
    max-width: 96vw;
    max-height: 86vh;
    object-fit: contain;
  }
  .g-voll-leiste {
    position: absolute;
    bottom: var(--a4);
    left: 50%;
    transform: translateX(-50%);
    display: flex;
    align-items: center;
    gap: var(--a2);
    background: rgba(20, 20, 24, 0.9);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: var(--r3);
    padding: var(--a2) var(--a3);
    color: #fff;
  }
  .g-voll-leiste .name {
    max-width: 30vw;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: 0.86rem;
  }
  .g-voll-leiste .zaehler {
    color: rgba(255, 255, 255, 0.6);
    font-size: 0.82rem;
  }
  .vk {
    border: none;
    background: transparent;
    color: #fff;
    cursor: pointer;
    font-size: 1rem;
    width: 32px;
    height: 32px;
    border-radius: var(--r1);
  }
  .vk:hover {
    background: rgba(255, 255, 255, 0.14);
  }
  .vk.aktiv {
    color: var(--akzent);
  }
  .sek {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: 0.82rem;
    color: rgba(255, 255, 255, 0.7);
  }
  .sek input {
    width: 42px;
    background: rgba(255, 255, 255, 0.1);
    border: 1px solid rgba(255, 255, 255, 0.15);
    color: #fff;
    border-radius: var(--r1);
    padding: 2px 4px;
    font: inherit;
    font-size: 0.82rem;
  }
</style>

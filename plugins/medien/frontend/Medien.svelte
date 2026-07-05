<script lang="ts">
  import { SvelteSet, SvelteMap } from "svelte/reactivity";
  import type { Browser } from "../../lib/browser.svelte";
  import type { Knoten } from "../../lib/types";
  import { symbol, groesseText } from "../../lib/format";
  import { waehleApp } from "../appzustand.svelte";
  import { player, spielen, aktuelleSpur, type Spur } from "../../lib/player.svelte";
  import {
    istBild, istAudio, formatKuerzel,
    thumbUrl, inlineUrl, streamUrl, ladeAlleMedien, type GMedium,
  } from "./medien";

  interface Props { browser: Browser; }
  let { browser }: Props = $props();

  type Anzeige = {
    id: string; name: string; groesse: number | null;
    pfad: { id: string; name: string }[] | null; typ: "bild" | "audio";
  };

  const kaputt = new SvelteSet<string>();
  const dauern = new SvelteMap<string, number>(); // Audio-Dauer, clientseitig geladen
  let modus = $state<"kachel_gross" | "kachel_klein" | "liste">("kachel_gross");
  let quelle = $state<"alle" | "ordner">("alle");
  let filter = $state<"alle" | "bild" | "audio">("alle");
  let alle = $state<GMedium[]>([]);
  let geladen = $state(false);
  let ladeFehler = $state("");

  async function ladeAlle() {
    ladeFehler = "";
    try { alle = await ladeAlleMedien(); } catch (e) { ladeFehler = (e as Error).message; }
    geladen = true;
  }
  $effect(() => { if (quelle === "alle" && !geladen) ladeAlle(); });

  // Audio ist keine Kachel-Sache: beim Umschalten auf "Audio" gleich in die Liste.
  function setzeFilter(f: "alle" | "bild" | "audio") {
    filter = f;
    if (f === "audio") modus = "liste";
  }

  const ordner = $derived(
    quelle === "ordner" ? browser.eintraege.filter((k) => k.typ === "ordner" || k.typ === "extern") : [],
  );
  const roh = $derived<Anzeige[]>(
    quelle === "alle"
      ? alle.map((m) => ({ id: m.id, name: m.name, groesse: m.groesse, pfad: m.pfad, typ: m.typ }))
      : browser.eintraege
          .filter((k) => k.typ === "datei" && (istBild(k.name) || istAudio(k.name)))
          .map((k) => ({ id: k.id, name: k.name, groesse: k.groesse ?? null, pfad: null, typ: (istBild(k.name) ? "bild" : "audio") as "bild" | "audio" })),
  );
  const medien = $derived(roh.filter((m) => filter === "alle" || m.typ === filter));
  const bilder = $derived(medien.filter((m) => m.typ === "bild"));
  const audios = $derived(medien.filter((m) => m.typ === "audio"));
  const thumbKante = $derived(modus === "kachel_klein" ? 200 : 400);
  const zahlBild = $derived(roh.filter((m) => m.typ === "bild").length);
  const zahlAudio = $derived(roh.filter((m) => m.typ === "audio").length);

  function pfadText(p: { id: string; name: string }[] | null) { return !p || !p.length ? "Meine Dateien" : p.map((x) => x.name).join(" / "); }
  function zumOrdner(m: Anzeige | null) { if (!m || !m.pfad) return; browser.oeffnePfad(m.pfad, m.id); waehleApp("dateien"); }
  function oeffneOrdner(k: Knoten) { browser.oeffnen(k); }
  function mmss(s: number | undefined) { if (s === undefined || !isFinite(s)) return "-"; const m = Math.floor(s / 60); const r = Math.floor(s % 60); return `${m}:${r.toString().padStart(2, "0")}`; }

  // --- Bild-Lightbox ---
  let vollIndex = $state<number | null>(null);
  const aktuellesBild = $derived(vollIndex === null ? null : (bilder[vollIndex] ?? null));
  function zeigeBild(m: Anzeige) { const i = bilder.findIndex((b) => b.id === m.id); if (i >= 0) vollIndex = i; }
  function schliesse() { vollIndex = null; }
  function bildWeiter() { if (vollIndex !== null && bilder.length) vollIndex = (vollIndex + 1) % bilder.length; }
  function bildZurueck() { if (vollIndex !== null && bilder.length) vollIndex = (vollIndex - 1 + bilder.length) % bilder.length; }

  // --- Audio: die Wiedergabe laeuft in der globalen Player-Leiste (App-Rahmen),
  // damit sie die Navigation ueberlebt. Hier wird nur gestartet + hervorgehoben.
  const spielId = $derived(aktuelleSpur()?.id ?? null);

  function spiele(m: Anzeige) {
    const spuren: Spur[] = audios.map((a) => ({ id: a.id, url: streamUrl(a.id), titel: a.name, pfad: a.pfad }));
    const i = spuren.findIndex((s) => s.id === m.id);
    if (i >= 0) spielen(spuren, i);
  }

  function taste(e: KeyboardEvent) {
    if (vollIndex !== null) { if (e.key === "Escape") schliesse(); else if (e.key === "ArrowRight") bildWeiter(); else if (e.key === "ArrowLeft") bildZurueck(); }
  }
</script>

<svelte:window onkeydown={taste} />

<div class="med-werkzeuge">
  <div class="seg">
    <button class:aktiv={quelle === "alle"} onclick={() => (quelle = "alle")}><i class="fa-solid fa-layer-group"></i> Alle Medien</button>
    <button class:aktiv={quelle === "ordner"} onclick={() => (quelle = "ordner")}><i class="fa-solid fa-folder"></i> Dieser Ordner</button>
  </div>
  <div class="seg">
    <button class:aktiv={filter === "alle"} onclick={() => setzeFilter("alle")}>Alle</button>
    <button class:aktiv={filter === "bild"} onclick={() => setzeFilter("bild")}><i class="fa-regular fa-image"></i> Bilder</button>
    <button class:aktiv={filter === "audio"} onclick={() => setzeFilter("audio")}><i class="fa-solid fa-music"></i> Audio</button>
  </div>
  <div class="seg">
    <button class:aktiv={modus === "kachel_gross"} title="Große Kacheln" onclick={() => (modus = "kachel_gross")}><i class="fa-solid fa-table-cells-large"></i></button>
    <button class:aktiv={modus === "kachel_klein"} title="Kleine Kacheln" onclick={() => (modus = "kachel_klein")}><i class="fa-solid fa-table-cells"></i></button>
    <button class:aktiv={modus === "liste"} title="Liste (mit Audiodaten)" onclick={() => (modus = "liste")}><i class="fa-solid fa-list"></i></button>
  </div>
  <span class="zahl">{zahlBild} Bilder &middot; {zahlAudio} Audios</span>
</div>

{#if (quelle === "alle" && !geladen) || (quelle === "ordner" && browser.laden)}
  <div class="med-leer"><i class="fa-solid fa-circle-notch fa-spin"></i></div>
{:else if quelle === "alle" && ladeFehler}
  <div class="med-leer"><i class="fa-solid fa-triangle-exclamation"></i><span>{ladeFehler}</span></div>
{:else if ordner.length === 0 && medien.length === 0}
  <div class="med-leer"><i class="fa-regular fa-image"></i><span>Keine Medien hier</span></div>
{:else if modus === "liste"}
  <div class="med-liste">
    <div class="ml-kopf">
      <span class="ml-c ml-name">Name</span>
      <span class="ml-c ml-dauer">Dauer</span>
      <span class="ml-c ml-format">Format</span>
      <span class="ml-c ml-groesse">Größe</span>
      <span class="ml-c ml-pfad">Ort</span>
    </div>
    {#each ordner as k (k.id)}
      <button class="ml-zeile ordner" ondblclick={() => oeffneOrdner(k)} onclick={() => oeffneOrdner(k)}>
        <span class="ml-c ml-name"><i class="sym fa-solid {symbol(k).icon}"></i> {k.name}</span>
        <span class="ml-c ml-dauer">-</span><span class="ml-c ml-format">Ordner</span>
        <span class="ml-c ml-groesse">-</span><span class="ml-c ml-pfad"></span>
      </button>
    {/each}
    {#each medien as m (m.id)}
      <button class="ml-zeile" class:spielt={spielId === m.id} onclick={() => (m.typ === "audio" ? spiele(m) : zeigeBild(m))}>
        <span class="ml-c ml-name">
          {#if m.typ === "audio"}
            <i class="sym audio fa-solid {spielId === m.id && player.laeuft ? 'fa-circle-pause' : 'fa-circle-play'}"></i>
            <audio preload="metadata" src={streamUrl(m.id)} onloadedmetadata={(e) => dauern.set(m.id, (e.currentTarget as HTMLAudioElement).duration)}></audio>
          {:else if kaputt.has(m.id)}
            <span class="sym"><i class="fa-regular fa-image"></i></span>
          {:else}
            <img class="ml-thumb" src={thumbUrl(m.id, 96)} alt={m.name} loading="lazy" onerror={() => kaputt.add(m.id)} />
          {/if}
          <span class="titel">{m.name}</span>
        </span>
        <span class="ml-c ml-dauer">{m.typ === "audio" ? mmss(dauern.get(m.id)) : "-"}</span>
        <span class="ml-c ml-format"><span class="badge">{formatKuerzel(m.name)}</span></span>
        <span class="ml-c ml-groesse">{m.groesse != null ? groesseText(m.groesse) : "-"}</span>
        <span class="ml-c ml-pfad" title={pfadText(m.pfad)}>{quelle === "alle" ? pfadText(m.pfad) : ""}</span>
      </button>
    {/each}
  </div>
{:else}
  <!-- Baut auf der Kern-Kachel auf (.grid/.kachel/.vorschau/.k-name aus app.css),
       damit sich das Raster GENAU wie im Datei-Browser verhaelt - kein eigenes,
       kollabierendes aspect-ratio-Raster mehr. -->
  <div class="grid med-grid" class:klein={modus === "kachel_klein"}>
    {#each ordner as k (k.id)}
      <button class="kachel med-kachel" ondblclick={() => oeffneOrdner(k)} onclick={() => oeffneOrdner(k)} title={k.name}>
        <div class="vorschau ordner"><i class="fa-solid {symbol(k).icon}"></i></div>
        <div class="k-name">{k.name}</div>
      </button>
    {/each}
    {#each medien as m (m.id)}
      {#if m.typ === "bild"}
        <button class="kachel med-kachel" onclick={() => zeigeBild(m)} title={m.name}>
          <div class="vorschau">
            {#if kaputt.has(m.id)}<i class="fa-regular fa-image"></i>
            {:else}<img class="med-voll" src={thumbUrl(m.id, thumbKante)} alt={m.name} loading="lazy" onerror={() => kaputt.add(m.id)} />{/if}
          </div>
          <div class="k-name">{m.name}</div>
          {#if quelle === "alle"}<div class="med-pfad">{pfadText(m.pfad)}</div>{/if}
        </button>
      {:else}
        <button class="kachel med-kachel" class:spielt={spielId === m.id} onclick={() => spiele(m)} title={m.name}>
          <div class="vorschau med-cover">
            <span class="med-format">{formatKuerzel(m.name)}</span>
            <i class="med-note fa-solid fa-music"></i>
            <span class="med-play"><i class="fa-solid {spielId === m.id && player.laeuft ? 'fa-pause' : 'fa-play'}"></i></span>
          </div>
          <div class="k-name">{m.name}</div>
          {#if quelle === "alle"}<div class="med-pfad">{pfadText(m.pfad)}</div>{/if}
        </button>
      {/if}
    {/each}
  </div>
{/if}

{#if aktuellesBild}
  <div class="m-voll" role="presentation" onclick={schliesse}>
    <img class="m-voll-bild" src={inlineUrl(aktuellesBild.id)} alt={aktuellesBild.name} role="presentation" onclick={(e) => e.stopPropagation()} />
    <div class="m-voll-leiste" role="presentation" onclick={(e) => e.stopPropagation()}>
      <button class="vk" aria-label="Zurück" onclick={bildZurueck}><i class="fa-solid fa-chevron-left"></i></button>
      <span class="name">{aktuellesBild.name}</span>
      <span class="zaehler">{(vollIndex ?? 0) + 1} / {bilder.length}</span>
      <button class="vk" aria-label="Weiter" onclick={bildWeiter}><i class="fa-solid fa-chevron-right"></i></button>
      {#if aktuellesBild.pfad}<button class="vk" title="Zum Ordner" aria-label="Zum Ordner" onclick={() => zumOrdner(aktuellesBild)}><i class="fa-solid fa-folder-open"></i></button>{/if}
      <button class="vk" aria-label="Schließen" onclick={schliesse}><i class="fa-solid fa-xmark"></i></button>
    </div>
  </div>
{/if}

<style>
  .med-werkzeuge { display: flex; align-items: center; gap: var(--a2); padding: var(--a2) var(--a4); flex-wrap: wrap; }
  .seg { display: inline-flex; gap: 2px; background: var(--flaeche-2); border: 1px solid var(--rand); border-radius: var(--r2); padding: 2px; }
  .seg button { border: none; background: transparent; color: var(--text-2); font: inherit; font-size: 0.84rem; padding: var(--a1) var(--a2); border-radius: var(--r1); cursor: pointer; display: inline-flex; align-items: center; gap: var(--a1); }
  .seg button.aktiv { background: var(--akzent-weich); color: var(--akzent-stark); }
  .zahl { margin-left: auto; color: var(--text-3); font-size: 0.82rem; }
  .med-leer { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: var(--a2); padding: var(--a5) 0; color: var(--text-3); font-size: 1.4rem; }
  .med-leer span { font-size: 0.9rem; }
  /* Medien-Kacheln bauen auf der Kern-Kachel auf (.grid/.kachel/.vorschau/.k-name
     in app.css) - KEIN eigenes Raster mehr. Feste Vorschauhoehe statt aspect-ratio
     (das hier im echten App-Kontext kollabierte). Nur medienspezifische Zusaetze. */
  .med-grid { grid-template-columns: repeat(auto-fill, minmax(170px, 1fr)); }
  .med-grid.klein { grid-template-columns: repeat(auto-fill, minmax(118px, 1fr)); }
  .med-kachel { cursor: pointer; text-align: left; font: inherit; color: var(--text); }
  .med-kachel .vorschau { height: 128px; }
  .med-grid.klein .vorschau { height: 88px; }
  .med-kachel.spielt { border-color: var(--akzent); background: var(--akzent-weich); }
  .med-voll { width: 100%; height: 100%; object-fit: cover; }
  .med-kachel .med-cover { background: linear-gradient(135deg, #6d5efc, #3b82f6); color: #fff; font-size: 1.7rem; position: relative; }
  /* Play-/Pause-Overlay auf der Audio-Kachel: bei Hover und beim laufenden Titel. */
  .med-cover .med-play { position: absolute; inset: 0; display: grid; place-items: center; font-size: 1.5rem; background: rgba(0, 0, 0, 0.28); opacity: 0; transition: opacity 0.15s ease; }
  .med-kachel:hover .med-play, .med-kachel.spielt .med-play { opacity: 1; }
  .med-format { position: absolute; top: 6px; right: 6px; font-size: 0.6rem; font-weight: 600; padding: 2px 7px; border-radius: 999px; background: rgba(0,0,0,0.42); color: #fff; }
  .med-pfad { font-size: 0.76rem; color: var(--akzent); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; margin-top: 2px; }

  /* Listenansicht (v.a. fuer Audio) */
  .med-liste { flex: 1; overflow-y: auto; padding: 0 var(--a4); }
  .ml-kopf, .ml-zeile { display: grid; grid-template-columns: minmax(0, 1fr) 70px 84px 96px minmax(0, 1.1fr); align-items: center; gap: var(--a3); }
  .ml-kopf { padding: var(--a2) var(--a2); font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.04em; color: var(--text-3); border-bottom: 1px solid var(--rand); position: sticky; top: 0; background: var(--flaeche); }
  .ml-zeile { width: 100%; border: none; background: transparent; cursor: pointer; text-align: left; color: var(--text); font: inherit; padding: var(--a1) var(--a2); border-radius: var(--r1); }
  .ml-zeile:hover { background: var(--flaeche-2); }
  .ml-zeile.spielt { background: var(--akzent-weich); }
  .ml-name { display: flex; align-items: center; gap: var(--a2); min-width: 0; }
  .ml-name .titel { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .ml-name .sym { width: 28px; text-align: center; color: var(--text-2); }
  .ml-name .sym.audio { color: var(--akzent); font-size: 1.15rem; }
  .ml-thumb { width: 40px; height: 40px; object-fit: cover; border-radius: var(--r1); flex: none; }
  .ml-dauer { font-variant-numeric: tabular-nums; color: var(--text-2); }
  .ml-groesse { color: var(--text-2); font-size: 0.85rem; }
  .ml-pfad { color: var(--akzent); font-size: 0.82rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .ml-format .badge { font-size: 0.66rem; font-weight: 600; padding: 2px 7px; border-radius: 999px; background: var(--flaeche-3); color: var(--text-2); }
  .ml-zeile audio { display: none; }

  .m-voll { position: fixed; inset: 0; background: rgba(0,0,0,0.92); display: flex; align-items: center; justify-content: center; z-index: 60; }
  .m-voll-bild { max-width: 96vw; max-height: 84vh; object-fit: contain; }
  .m-voll-leiste { position: absolute; bottom: calc(84px + var(--a3)); left: 50%; transform: translateX(-50%); display: flex; align-items: center; gap: var(--a2); background: rgba(20,20,24,0.9); border: 1px solid rgba(255,255,255,0.12); border-radius: var(--r3); padding: var(--a2) var(--a3); color: #fff; }
  .m-voll-leiste .name { max-width: 30vw; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 0.86rem; }
  .m-voll-leiste .zaehler { color: rgba(255,255,255,0.6); font-size: 0.82rem; }
  .vk { border: none; background: transparent; color: #fff; cursor: pointer; font-size: 1rem; width: 32px; height: 32px; border-radius: var(--r1); }
  .vk:hover { background: rgba(255,255,255,0.14); }
</style>

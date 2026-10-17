<script lang="ts">
  import { onMount } from "svelte";
  import { SvelteSet, SvelteMap } from "svelte/reactivity";
  import type { Browser } from "../browser.svelte";
  import type { Knoten, Medium } from "../types";
  import * as api from "../api";
  import { symbol, groesseText } from "../format";
  import { player, aktuelleSpur } from "../player.svelte";
  import { beiAenderung } from "../zustand.svelte";
  import { medienEinstellung as e, type Medienfilter } from "../ansicht.svelte";
  import { oeffneVollansicht } from "../vorschau.svelte";
  import { ausKnoten, ausMedium, formatKuerzel, stromUrl, vorschauUrl, type MedienEintrag } from "./adressen";
  import { medienOeffnen } from "./oeffnen";

  // Medienansicht: alle eigenen Medien im Baum oder die des offenen Ordners, als
  // Kacheln oder Liste. Bilder und Videos öffnen in der zentralen Vollansicht,
  // Audio spielt in der Player-Leiste. Die Einstellungen liegen ausserhalb des
  // Bauteils und überleben so den Wechsel zu den Dateien und zurück.
  interface Props {
    browser: Browser;
  }
  let { browser }: Props = $props();

  const kaputt = new SvelteSet<string>();
  const dauern = new SvelteMap<string, number>(); // Audio-Dauer, im Browser ermittelt
  let alle = $state<Medium[]>([]);
  let geladen = $state(false);
  let ladeFehler = $state("");

  async function ladeAlle() {
    try {
      alle = await api.alleMedien();
      ladeFehler = "";
    } catch (f) {
      ladeFehler = (f as Error).message;
    }
    geladen = true;
  }
  $effect(() => {
    if (e.quelle === "alle" && !geladen) ladeAlle();
  });
  // Live: jede Änderung im Konto zieht "Alle Medien" nach (der Ordner zieht über die Fläche nach).
  onMount(() => beiAenderung(() => {
    if (e.quelle === "alle") ladeAlle();
  }));

  // Audio ist keine Kachel-Sache: beim Umschalten auf "Audio" gleich in die Liste.
  function setzeFilter(f: Medienfilter) {
    e.filter = f;
    if (f === "audio") e.darstellung = "liste";
  }

  const ordner = $derived(
    e.quelle === "ordner" ? browser.eintraege.filter((k) => k.typ === "ordner" || k.typ === "extern") : [],
  );
  const roh = $derived<MedienEintrag[]>(
    e.quelle === "alle"
      ? alle.map(ausMedium)
      : browser.eintraege
          .map((k) => ausKnoten(k, browser.bereich === "dateien" ? browser.pfad.slice(1) : null))
          .filter((m): m is MedienEintrag => m !== null),
  );
  const medien = $derived(roh.filter((m) => e.filter === "alle" || m.art === e.filter));
  const bilder = $derived(medien.filter((m) => m.art === "bild"));
  const zahlBild = $derived(roh.filter((m) => m.art === "bild").length);
  const zahlAudio = $derived(roh.filter((m) => m.art === "audio").length);
  const zahlVideo = $derived(roh.filter((m) => m.art === "video").length);

  function pfadText(p: MedienEintrag["pfad"]) {
    return !p || !p.length ? "Meine Dateien" : p.map((x) => x.name).join(" / ");
  }
  function oeffneOrdner(k: Knoten) {
    browser.oeffnen(k);
  }
  function mmss(s: number | undefined) {
    if (s === undefined || !isFinite(s)) return "-";
    const m = Math.floor(s / 60);
    const r = Math.floor(s % 60);
    return `${m}:${r.toString().padStart(2, "0")}`;
  }
  function oeffne(m: MedienEintrag) {
    medienOeffnen(medien, medien.indexOf(m));
  }
  function starteDiashow() {
    if (bilder.length) oeffneVollansicht(bilder, 0, true);
  }

  const spielId = $derived(aktuelleSpur()?.id ?? null);
</script>

<div class="med-werkzeuge">
  <div class="seg">
    <button class:aktiv={e.quelle === "alle"} onclick={() => (e.quelle = "alle")}><i class="fa-solid fa-layer-group"></i> Alle Medien</button>
    <button class:aktiv={e.quelle === "ordner"} onclick={() => (e.quelle = "ordner")}><i class="fa-solid fa-folder"></i> Dieser Ordner</button>
  </div>
  <div class="seg">
    <button class:aktiv={e.filter === "alle"} onclick={() => setzeFilter("alle")}>Alle</button>
    <button class:aktiv={e.filter === "bild"} onclick={() => setzeFilter("bild")}><i class="fa-regular fa-image"></i> Bilder</button>
    <button class:aktiv={e.filter === "audio"} onclick={() => setzeFilter("audio")}><i class="fa-solid fa-music"></i> Audio</button>
    <button class:aktiv={e.filter === "video"} onclick={() => setzeFilter("video")}><i class="fa-solid fa-film"></i> Video</button>
  </div>
  <div class="seg">
    <button class:aktiv={e.darstellung === "kacheln"} title="Große Kacheln" onclick={() => (e.darstellung = "kacheln")}><i class="fa-solid fa-table-cells-large"></i></button>
    <button class:aktiv={e.darstellung === "liste"} title="Liste mit Details" onclick={() => (e.darstellung = "liste")}><i class="fa-solid fa-list"></i></button>
  </div>
  {#if bilder.length > 0}
    <button class="med-diashow" title="Diashow starten" onclick={starteDiashow}><i class="fa-solid fa-play"></i> Diashow</button>
  {/if}
  <span class="zahl">{zahlBild} Bilder &middot; {zahlAudio} Audios &middot; {zahlVideo} Videos</span>
</div>

{#if (e.quelle === "alle" && !geladen) || (e.quelle === "ordner" && browser.laden)}
  <div class="med-leer"><i class="fa-solid fa-circle-notch fa-spin"></i></div>
{:else if e.quelle === "alle" && ladeFehler && alle.length === 0}
  <div class="med-leer"><i class="fa-solid fa-triangle-exclamation"></i><span>{ladeFehler}</span></div>
{:else if ordner.length === 0 && medien.length === 0}
  <div class="med-leer"><i class="fa-regular fa-image"></i><span>Keine Medien hier</span></div>
{:else if e.darstellung === "liste"}
  <div class="med-liste">
    <div class="ml-kopf">
      <span class="ml-c ml-name">Name</span>
      <span class="ml-c ml-dauer">Dauer</span>
      <span class="ml-c ml-format">Format</span>
      <span class="ml-c ml-groesse">Größe</span>
      <span class="ml-c ml-pfad">Ort</span>
    </div>
    {#each ordner as k (k.id)}
      <button class="ml-zeile ordner" onclick={() => oeffneOrdner(k)}>
        <span class="ml-c ml-name"><i class="sym fa-solid {symbol(k).icon}"></i> {k.name}</span>
        <span class="ml-c ml-dauer">-</span><span class="ml-c ml-format">Ordner</span>
        <span class="ml-c ml-groesse">-</span><span class="ml-c ml-pfad"></span>
      </button>
    {/each}
    {#each medien as m (m.id)}
      <button class="ml-zeile" class:spielt={spielId === m.id} onclick={() => oeffne(m)}>
        <span class="ml-c ml-name">
          {#if m.art === "audio"}
            <i class="sym audio fa-solid {spielId === m.id && player.laeuft ? 'fa-circle-pause' : 'fa-circle-play'}"></i>
            <audio preload="metadata" src={stromUrl(m)} onloadedmetadata={(ev) => dauern.set(m.id, (ev.currentTarget as HTMLAudioElement).duration)}></audio>
          {:else if m.art === "video"}
            <i class="sym video fa-solid fa-circle-play"></i>
          {:else if kaputt.has(m.id)}
            <span class="sym"><i class="fa-regular fa-image"></i></span>
          {:else}
            <img class="ml-thumb" src={vorschauUrl(m, "klein")} alt={m.name} loading="lazy" onerror={() => kaputt.add(m.id)} />
          {/if}
          <span class="titel">{m.name}</span>
        </span>
        <span class="ml-c ml-dauer">{m.art === "audio" ? mmss(dauern.get(m.id)) : "-"}</span>
        <span class="ml-c ml-format"><span class="badge">{formatKuerzel(m.name)}</span></span>
        <span class="ml-c ml-groesse">{m.groesse != null ? groesseText(m.groesse) : "-"}</span>
        <span class="ml-c ml-pfad" title={pfadText(m.pfad)}>{e.quelle === "alle" ? pfadText(m.pfad) : ""}</span>
      </button>
    {/each}
  </div>
{:else}
  <!-- Baut auf der Kern-Kachel auf (.grid/.kachel/.vorschau/.k-name aus app.css),
       damit sich das Raster genau wie im Datei-Browser verhaelt. -->
  <div class="grid med-grid">
    {#each ordner as k (k.id)}
      <button class="kachel med-kachel" onclick={() => oeffneOrdner(k)} title={k.name}>
        <div class="vorschau ordner"><i class="fa-solid {symbol(k).icon}"></i></div>
        <div class="k-name">{k.name}</div>
      </button>
    {/each}
    {#each medien as m (m.id)}
      {#if m.art === "bild"}
        <button class="kachel med-kachel" onclick={() => oeffne(m)} title={m.name}>
          <div class="vorschau">
            {#if kaputt.has(m.id)}<i class="fa-regular fa-image"></i>
            {:else}<img class="med-voll" src={vorschauUrl(m)} alt={m.name} loading="lazy" onerror={() => kaputt.add(m.id)} />{/if}
          </div>
          <div class="k-name">{m.name}</div>
          {#if e.quelle === "alle"}<div class="med-pfad">{pfadText(m.pfad)}</div>{/if}
        </button>
      {:else if m.art === "video"}
        <button class="kachel med-kachel" onclick={() => oeffne(m)} title={m.name}>
          <div class="vorschau med-cover med-video" class:ohne-bild={kaputt.has(m.id)}>
            {#if kaputt.has(m.id)}
              <i class="med-note fa-solid fa-film"></i>
            {:else}
              <!-- Standbild aus dem Video; ohne ffmpeg fällt es aufs Symbol zurück. -->
              <img class="med-voll" src={vorschauUrl(m)} alt={m.name} loading="lazy" onerror={() => kaputt.add(m.id)} />
            {/if}
            <span class="med-format">{formatKuerzel(m.name)}</span>
            <span class="med-play med-video-play"><i class="fa-solid fa-play"></i></span>
          </div>
          <div class="k-name">{m.name}</div>
          {#if e.quelle === "alle"}<div class="med-pfad">{pfadText(m.pfad)}</div>{/if}
        </button>
      {:else}
        <button class="kachel med-kachel" class:spielt={spielId === m.id} onclick={() => oeffne(m)} title={m.name}>
          <div class="vorschau med-cover">
            <span class="med-format">{formatKuerzel(m.name)}</span>
            <i class="med-note fa-solid fa-music"></i>
            <span class="med-play"><i class="fa-solid {spielId === m.id && player.laeuft ? 'fa-pause' : 'fa-play'}"></i></span>
          </div>
          <div class="k-name">{m.name}</div>
          {#if e.quelle === "alle"}<div class="med-pfad">{pfadText(m.pfad)}</div>{/if}
        </button>
      {/if}
    {/each}
  </div>
{/if}

<style>
  .med-werkzeuge { display: flex; align-items: center; gap: var(--a2); padding: var(--a2) var(--a4); flex-wrap: wrap; }
  .seg { display: inline-flex; gap: 2px; background: var(--flaeche-2); border: 1px solid var(--rand); border-radius: var(--r2); padding: 2px; }
  .seg button { border: none; background: transparent; color: var(--text-2); font: inherit; font-size: 0.84rem; padding: var(--a1) var(--a2); border-radius: var(--r1); cursor: pointer; display: inline-flex; align-items: center; gap: var(--a1); }
  .seg button.aktiv { background: var(--akzent-weich); color: var(--akzent-stark); }
  .med-diashow { border: 1px solid var(--rand); background: transparent; color: var(--text-2); font: inherit; font-size: 0.84rem; padding: var(--a1) var(--a2); border-radius: var(--r1); cursor: pointer; display: inline-flex; align-items: center; gap: var(--a1); }
  .med-diashow:hover { background: var(--flaeche-3); }
  .zahl { margin-left: auto; color: var(--text-3); font-size: 0.82rem; }
  .med-leer { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: var(--a2); padding: var(--a5) 0; color: var(--text-3); font-size: 1.4rem; }
  .med-leer span { font-size: 0.9rem; }
  /* Medien-Kacheln bauen auf der Kern-Kachel auf (.grid/.kachel/.vorschau/.k-name
     in app.css) - KEIN eigenes Raster mehr. Feste Vorschauhoehe statt aspect-ratio
     (das hier im echten App-Kontext kollabierte). Nur medienspezifische Zusaetze. */
  .med-grid { grid-template-columns: repeat(auto-fill, minmax(170px, 1fr)); }
  .med-kachel { cursor: pointer; text-align: left; font: inherit; color: var(--text); }
  .med-kachel .vorschau { height: 128px; }
  .med-kachel.spielt { border-color: var(--akzent); background: var(--akzent-weich); }
  .med-voll { width: 100%; height: 100%; object-fit: cover; }
  .med-kachel .med-cover { background: linear-gradient(135deg, #6d5efc, #3b82f6); color: #fff; font-size: 1.7rem; position: relative; }
  /* Video klar von Audio unterscheidbar (anderer Farbverlauf, Film statt Note). */
  /* Video mit Standbild: schwarzer Grund; ohne Standbild der Farbverlauf. */
  .med-kachel .med-cover.med-video { background: #000; font-size: 1.7rem; }
  .med-kachel .med-cover.med-video.ohne-bild { background: linear-gradient(135deg, #1f2937, #0f766e); }
  /* Beim Video ist das Abspielzeichen dauerhaft sichtbar - sonst sieht das
     Standbild wie ein Foto aus. */
  .med-cover .med-play.med-video-play {
    inset: auto; width: 40px; height: 40px; border-radius: 50%;
    background: rgba(0, 0, 0, 0.5); border: 2px solid rgba(255, 255, 255, 0.85);
    font-size: 0.9rem; opacity: 1;
  }
  .med-kachel:hover .med-play.med-video-play { background: rgba(0, 0, 0, 0.75); }
  .ml-name .sym.video { color: var(--akzent); font-size: 1.15rem; }
  /* Play-/Pause-Overlay auf der Audio-Kachel: bei Hover und beim laufenden Titel. */
  .med-cover .med-play { position: absolute; inset: 0; display: grid; place-items: center; font-size: 1.5rem; background: rgba(0, 0, 0, 0.28); opacity: 0; transition: opacity 0.15s ease; }
  .med-kachel:hover .med-play, .med-kachel.spielt .med-play { opacity: 1; }
  .med-format { position: absolute; top: 6px; right: 6px; font-size: 0.6rem; font-weight: 600; padding: 2px 7px; border-radius: 999px; background: rgba(0,0,0,0.42); color: #fff; }
  .med-pfad { font-size: 0.76rem; color: var(--akzent); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; margin-top: 2px; }

  /* Listenansicht (v.a. für Audio) */
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

</style>

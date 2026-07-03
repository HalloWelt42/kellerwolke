<script lang="ts">
  import { SvelteSet } from "svelte/reactivity";
  import type { Browser } from "../../lib/browser.svelte";
  import type { Knoten } from "../../lib/types";
  import { symbol } from "../../lib/format";
  import { waehleApp } from "../appzustand.svelte";
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
  let modus = $state<"kachel_gross" | "kachel_klein">("kachel_gross");
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

  // --- Bild-Lightbox ---
  let vollIndex = $state<number | null>(null);
  const aktuellesBild = $derived(vollIndex === null ? null : (bilder[vollIndex] ?? null));
  function zeigeBild(m: Anzeige) { const i = bilder.findIndex((b) => b.id === m.id); if (i >= 0) vollIndex = i; }
  function schliesse() { vollIndex = null; }
  function bildWeiter() { if (vollIndex !== null && bilder.length) vollIndex = (vollIndex + 1) % bilder.length; }
  function bildZurueck() { if (vollIndex !== null && bilder.length) vollIndex = (vollIndex - 1 + bilder.length) % bilder.length; }

  // --- Audio-Player ---
  let audioEl: HTMLAudioElement;
  let spielId = $state<string | null>(null);
  let laeuft = $state(false);
  let zeit = $state(0);
  let dauer = $state(0);
  const aktAudio = $derived(audios.find((a) => a.id === spielId) ?? null);

  function spiele(m: Anzeige) {
    if (spielId === m.id) { toggle(); return; }
    spielId = m.id;
    if (audioEl) { audioEl.src = streamUrl(m.id); audioEl.play().catch(() => {}); }
  }
  function toggle() { if (!audioEl) return; if (audioEl.paused) audioEl.play().catch(() => {}); else audioEl.pause(); }
  function audioWeiter() { if (!aktAudio || !audios.length) return; const i = audios.findIndex((a) => a.id === aktAudio.id); spiele(audios[(i + 1) % audios.length]); }
  function amEnde() {
    // Am Ende einer Datei zur naechsten - aber NICHT endlos die einzige wiederholen.
    if (!aktAudio) return;
    const i = audios.findIndex((a) => a.id === aktAudio.id);
    if (i >= 0 && i < audios.length - 1) spiele(audios[i + 1]);
    else laeuft = false;
  }
  function audioZurueck() { if (!aktAudio || !audios.length) return; const i = audios.findIndex((a) => a.id === aktAudio.id); spiele(audios[(i - 1 + audios.length) % audios.length]); }
  function suche(e: MouseEvent) { if (!audioEl || !dauer) return; const r = (e.currentTarget as HTMLElement).getBoundingClientRect(); audioEl.currentTime = ((e.clientX - r.left) / r.width) * dauer; }
  function mmss(s: number) { if (!isFinite(s)) return "0:00"; const m = Math.floor(s / 60); const r = Math.floor(s % 60); return `${m}:${r.toString().padStart(2, "0")}`; }

  function taste(e: KeyboardEvent) {
    if (vollIndex !== null) { if (e.key === "Escape") schliesse(); else if (e.key === "ArrowRight") bildWeiter(); else if (e.key === "ArrowLeft") bildZurueck(); }
  }
</script>

<svelte:window onkeydown={taste} />
<audio
  bind:this={audioEl}
  onplay={() => (laeuft = true)}
  onpause={() => (laeuft = false)}
  ontimeupdate={() => (zeit = audioEl.currentTime)}
  onloadedmetadata={() => (dauer = audioEl.duration)}
  onended={amEnde}
></audio>

<div class="med-werkzeuge">
  <div class="seg">
    <button class:aktiv={quelle === "alle"} onclick={() => (quelle = "alle")}><i class="fa-solid fa-layer-group"></i> Alle Medien</button>
    <button class:aktiv={quelle === "ordner"} onclick={() => (quelle = "ordner")}><i class="fa-solid fa-folder"></i> Dieser Ordner</button>
  </div>
  <div class="seg">
    <button class:aktiv={filter === "alle"} onclick={() => (filter = "alle")}>Alle</button>
    <button class:aktiv={filter === "bild"} onclick={() => (filter = "bild")}><i class="fa-regular fa-image"></i> Bilder</button>
    <button class:aktiv={filter === "audio"} onclick={() => (filter = "audio")}><i class="fa-solid fa-music"></i> Audio</button>
  </div>
  <div class="seg">
    <button class:aktiv={modus === "kachel_gross"} title="Große Kacheln" onclick={() => (modus = "kachel_gross")}><i class="fa-solid fa-table-cells-large"></i></button>
    <button class:aktiv={modus === "kachel_klein"} title="Kleine Kacheln" onclick={() => (modus = "kachel_klein")}><i class="fa-solid fa-table-cells"></i></button>
  </div>
  <span class="zahl">{zahlBild} Bilder &middot; {zahlAudio} Audios</span>
</div>

{#if (quelle === "alle" && !geladen) || (quelle === "ordner" && browser.laden)}
  <div class="med-leer"><i class="fa-solid fa-circle-notch fa-spin"></i></div>
{:else if quelle === "alle" && ladeFehler}
  <div class="med-leer"><i class="fa-solid fa-triangle-exclamation"></i><span>{ladeFehler}</span></div>
{:else if ordner.length === 0 && medien.length === 0}
  <div class="med-leer"><i class="fa-regular fa-image"></i><span>Keine Medien hier</span></div>
{:else}
  <div class="med-gitter" class:klein={modus === "kachel_klein"}>
    {#each ordner as k (k.id)}
      <button class="m-ordner" ondblclick={() => oeffneOrdner(k)} onclick={() => oeffneOrdner(k)} title={k.name}>
        <i class="fa-solid {symbol(k).icon}"></i><span class="titel">{k.name}</span>
      </button>
    {/each}
    {#each medien as m (m.id)}
      {#if m.typ === "bild"}
        <button class="m-bild" onclick={() => zeigeBild(m)} title={m.name}>
          {#if kaputt.has(m.id)}
            <div class="m-platz"><i class="fa-regular fa-image"></i></div>
          {:else}
            <img src={thumbUrl(m.id, thumbKante)} alt={m.name} loading="lazy" onerror={() => kaputt.add(m.id)} />
          {/if}
        </button>
      {:else}
        <button class="m-audio" class:spielt={spielId === m.id} onclick={() => spiele(m)} title={m.name}>
          <div class="m-cover">
            <span class="m-format">{formatKuerzel(m.name)}</span>
            <i class="fa-solid {spielId === m.id && laeuft ? 'fa-volume-high' : 'fa-music'}"></i>
          </div>
          <div class="m-info">
            <span class="titel">{m.name}</span>
            {#if quelle === "alle"}<span class="pfad">{pfadText(m.pfad)}</span>{/if}
          </div>
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

{#if aktAudio}
  <div class="player">
    <div class="p-jetzt">
      <div class="p-cover"><i class="fa-solid fa-music"></i></div>
      <div class="p-text"><div class="p-titel">{aktAudio.name}</div><div class="p-pfad">{pfadText(aktAudio.pfad)}</div></div>
      {#if aktAudio.pfad}<button class="p-mini" title="Zum Ordner" aria-label="Zum Ordner" onclick={() => zumOrdner(aktAudio)}><i class="fa-solid fa-folder-open"></i></button>{/if}
    </div>
    <div class="p-mitte">
      <div class="p-tasten">
        <button aria-label="Zurück" onclick={audioZurueck}><i class="fa-solid fa-backward-step"></i></button>
        <button class="gross" aria-label={laeuft ? "Pause" : "Abspielen"} onclick={toggle}><i class="fa-solid {laeuft ? 'fa-pause' : 'fa-play'}"></i></button>
        <button aria-label="Weiter" onclick={audioWeiter}><i class="fa-solid fa-forward-step"></i></button>
      </div>
      <div class="p-fortschritt">
        <span class="p-zeit">{mmss(zeit)}</span>
        <div class="p-spur" role="slider" tabindex="0" aria-label="Position" aria-valuenow={Math.floor(zeit)} onclick={suche}>
          <div class="p-fuell" style="width:{dauer ? (zeit / dauer) * 100 : 0}%"></div>
        </div>
        <span class="p-zeit">{mmss(dauer)}</span>
      </div>
    </div>
    <div class="p-rechts"><button aria-label="Schließen" onclick={() => { if (audioEl) { audioEl.pause(); audioEl.currentTime = 0; } spielId = null; laeuft = false; }}><i class="fa-solid fa-xmark"></i></button></div>
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
  .med-gitter { flex: 1; overflow-y: auto; display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: var(--a3); padding: var(--a3) var(--a4) 104px; align-content: start; }
  .med-gitter.klein { grid-template-columns: repeat(auto-fill, minmax(128px, 1fr)); gap: var(--a2); }
  .m-bild { position: relative; aspect-ratio: 1; border: none; padding: 0; border-radius: var(--r2); overflow: hidden; cursor: pointer; background: var(--flaeche-2); }
  .m-bild img { width: 100%; height: 100%; object-fit: cover; display: block; }
  .m-platz { width: 100%; height: 100%; display: grid; place-items: center; color: var(--text-3); font-size: 1.8rem; }
  .m-audio { aspect-ratio: 1; border: 1px solid var(--rand); border-radius: var(--r2); background: var(--flaeche); display: flex; flex-direction: column; overflow: hidden; cursor: pointer; padding: 0; text-align: left; }
  .m-audio:hover { border-color: var(--rand-stark); }
  .m-audio.spielt { border-color: var(--akzent); }
  .m-cover { flex: 1; display: grid; place-items: center; color: #fff; font-size: 2rem; position: relative; background: linear-gradient(135deg, #6d5efc, #3b82f6); }
  .m-format { position: absolute; top: 8px; right: 8px; font-size: 0.6rem; font-weight: 600; padding: 2px 7px; border-radius: 999px; background: rgba(0,0,0,0.42); color: #fff; }
  .m-info { padding: var(--a2) var(--a3); }
  .m-info .titel { font-size: 0.84rem; font-weight: 600; color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .m-info .pfad { font-size: 0.76rem; color: var(--akzent); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .m-ordner { border: 1px solid var(--rand); background: var(--flaeche-2); border-radius: var(--r2); cursor: pointer; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: var(--a2); aspect-ratio: 1; color: var(--akzent); font-size: 2rem; }
  .m-ordner .titel { font-size: 0.8rem; color: var(--text); max-width: 90%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .m-voll { position: fixed; inset: 0; background: rgba(0,0,0,0.92); display: flex; align-items: center; justify-content: center; z-index: 60; }
  .m-voll-bild { max-width: 96vw; max-height: 84vh; object-fit: contain; }
  .m-voll-leiste { position: absolute; bottom: calc(84px + var(--a3)); left: 50%; transform: translateX(-50%); display: flex; align-items: center; gap: var(--a2); background: rgba(20,20,24,0.9); border: 1px solid rgba(255,255,255,0.12); border-radius: var(--r3); padding: var(--a2) var(--a3); color: #fff; }
  .m-voll-leiste .name { max-width: 30vw; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 0.86rem; }
  .m-voll-leiste .zaehler { color: rgba(255,255,255,0.6); font-size: 0.82rem; }
  .vk { border: none; background: transparent; color: #fff; cursor: pointer; font-size: 1rem; width: 32px; height: 32px; border-radius: var(--r1); }
  .vk:hover { background: rgba(255,255,255,0.14); }
  .player { position: fixed; left: 0; right: 0; bottom: 0; height: 78px; display: grid; grid-template-columns: minmax(170px, 1fr) minmax(300px, 1.6fr) auto; align-items: center; gap: var(--a4); padding: 0 var(--a4); background: var(--flaeche); border-top: 1px solid var(--rand); z-index: 50; }
  .p-jetzt { display: flex; align-items: center; gap: var(--a3); min-width: 0; }
  .p-cover { width: 48px; height: 48px; border-radius: var(--r2); display: grid; place-items: center; color: #fff; font-size: 1.1rem; flex: none; background: linear-gradient(135deg, #6d5efc, #3b82f6); }
  .p-text { min-width: 0; }
  .p-titel { font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .p-pfad { font-size: 0.78rem; color: var(--text-3); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .p-mini, .p-rechts button { border: none; background: transparent; color: var(--text-2); cursor: pointer; font-size: 0.95rem; }
  .p-mini:hover, .p-rechts button:hover { color: var(--text); }
  .p-mitte { display: flex; flex-direction: column; align-items: center; gap: 5px; }
  .p-tasten { display: flex; align-items: center; gap: var(--a3); }
  .p-tasten button { border: none; background: transparent; color: var(--text-2); cursor: pointer; font-size: 1rem; width: 34px; height: 34px; border-radius: 50%; }
  .p-tasten button:hover { background: var(--flaeche-2); color: var(--text); }
  .p-tasten .gross { width: 42px; height: 42px; background: var(--akzent); color: var(--akzent-text); }
  .p-tasten .gross:hover { background: var(--akzent-stark); }
  .p-fortschritt { display: flex; align-items: center; gap: var(--a2); width: 100%; max-width: 520px; }
  .p-zeit { font-size: 0.75rem; color: var(--text-3); min-width: 34px; text-align: center; }
  .p-spur { flex: 1; height: 5px; border-radius: 3px; background: var(--flaeche-3); position: relative; cursor: pointer; }
  .p-fuell { position: absolute; left: 0; top: 0; bottom: 0; background: var(--akzent); border-radius: 3px; }
  .p-rechts { justify-self: end; }
</style>

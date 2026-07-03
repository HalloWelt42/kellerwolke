<script lang="ts">
  // Durchgehende Player-Leiste am unteren Rand - eigene Optik (kein natives
  // <audio controls>). Wird einmalig von App.svelte gerendert und ueberlebt so
  // jede Navigation.
  import { player, aktuelleSpur, spurWeiter, spurZurueck, playerBeenden } from "./player.svelte";
  import { haupt } from "./zustand.svelte";
  import { waehleApp } from "../plugins/appzustand.svelte";

  let audioEl: HTMLAudioElement;
  let geladeneUrl = "";
  const spur = $derived(aktuelleSpur());

  // Nur bei echtem Spurwechsel neu laden + abspielen (nicht bei jedem Re-Render).
  $effect(() => {
    const s = spur;
    if (!audioEl) return;
    if (s && s.url !== geladeneUrl) {
      geladeneUrl = s.url;
      audioEl.src = s.url;
      audioEl.play().catch(() => {});
    } else if (!s) {
      geladeneUrl = "";
      audioEl.pause();
      audioEl.removeAttribute("src");
    }
  });

  function toggle() { if (!audioEl) return; if (audioEl.paused) audioEl.play().catch(() => {}); else audioEl.pause(); }
  function suche(e: MouseEvent) {
    if (!audioEl || !player.dauer) return;
    const r = (e.currentTarget as HTMLElement).getBoundingClientRect();
    audioEl.currentTime = ((e.clientX - r.left) / r.width) * player.dauer;
  }
  function mmss(s: number) { if (!isFinite(s)) return "0:00"; const m = Math.floor(s / 60); const r = Math.floor(s % 60); return `${m}:${r.toString().padStart(2, "0")}`; }
  function zumOrdner() { if (!spur?.pfad) return; haupt.oeffnePfad(spur.pfad, spur.id); waehleApp("dateien"); }
</script>

<audio
  bind:this={audioEl}
  onplay={() => (player.laeuft = true)}
  onpause={() => (player.laeuft = false)}
  ontimeupdate={() => (player.zeit = audioEl.currentTime)}
  onloadedmetadata={() => (player.dauer = audioEl.duration)}
  onended={spurWeiter}
></audio>

{#if spur}
  <div class="spieler" role="region" aria-label="Wiedergabe">
    <div class="s-jetzt">
      <div class="s-cover"><i class="fa-solid fa-music"></i></div>
      <div class="s-text">
        <div class="s-titel">{spur.titel}</div>
        {#if spur.pfad}<div class="s-pfad">{spur.pfad.length ? spur.pfad.map((x) => x.name).join(" / ") : "Meine Dateien"}</div>{/if}
      </div>
      {#if spur.pfad}<button class="s-mini" title="Zum Ordner" aria-label="Zum Ordner" onclick={zumOrdner}><i class="fa-solid fa-folder-open"></i></button>{/if}
    </div>
    <div class="s-mitte">
      <div class="s-tasten">
        <button aria-label="Zurück" onclick={spurZurueck}><i class="fa-solid fa-backward-step"></i></button>
        <button class="gross" aria-label={player.laeuft ? "Pause" : "Abspielen"} onclick={toggle}><i class="fa-solid {player.laeuft ? 'fa-pause' : 'fa-play'}"></i></button>
        <button aria-label="Weiter" onclick={spurWeiter}><i class="fa-solid fa-forward-step"></i></button>
      </div>
      <div class="s-fortschritt">
        <span class="s-zeit">{mmss(player.zeit)}</span>
        <div class="s-spur" role="slider" tabindex="0" aria-label="Position" aria-valuenow={Math.floor(player.zeit)} onclick={suche}><div class="s-fuell" style="width:{player.dauer ? (player.zeit / player.dauer) * 100 : 0}%"></div></div>
        <span class="s-zeit">{mmss(player.dauer)}</span>
      </div>
    </div>
    <div class="s-rechts"><button aria-label="Schließen" onclick={playerBeenden}><i class="fa-solid fa-xmark"></i></button></div>
  </div>
{/if}

<style>
  .spieler { position: fixed; left: 0; right: 0; bottom: 0; height: 78px; display: grid; grid-template-columns: minmax(170px, 1fr) minmax(300px, 1.6fr) auto; align-items: center; gap: var(--a4); padding: 0 var(--a4); background: var(--flaeche); border-top: 1px solid var(--rand); z-index: 55; }
  .s-jetzt { display: flex; align-items: center; gap: var(--a3); min-width: 0; }
  .s-cover { width: 48px; height: 48px; border-radius: var(--r2); display: grid; place-items: center; color: #fff; font-size: 1.1rem; flex: none; background: linear-gradient(135deg, #6d5efc, #3b82f6); }
  .s-text { min-width: 0; }
  .s-titel { font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .s-pfad { font-size: 0.78rem; color: var(--text-3); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .s-mini, .s-rechts button { border: none; background: transparent; color: var(--text-2); cursor: pointer; font-size: 0.95rem; }
  .s-mini:hover, .s-rechts button:hover { color: var(--text); }
  .s-mitte { display: flex; flex-direction: column; align-items: center; gap: 5px; }
  .s-tasten { display: flex; align-items: center; gap: var(--a3); }
  .s-tasten button { border: none; background: transparent; color: var(--text-2); cursor: pointer; font-size: 1rem; width: 34px; height: 34px; border-radius: 50%; }
  .s-tasten button:hover { background: var(--flaeche-2); color: var(--text); }
  .s-tasten .gross { width: 42px; height: 42px; background: var(--akzent); color: var(--akzent-text); }
  .s-tasten .gross:hover { background: var(--akzent-stark); }
  .s-fortschritt { display: flex; align-items: center; gap: var(--a2); width: 100%; max-width: 520px; }
  .s-zeit { font-size: 0.75rem; color: var(--text-3); min-width: 34px; text-align: center; font-variant-numeric: tabular-nums; }
  .s-spur { flex: 1; height: 5px; border-radius: 3px; background: var(--flaeche-3); position: relative; cursor: pointer; }
  .s-fuell { position: absolute; left: 0; top: 0; bottom: 0; background: var(--akzent); border-radius: 3px; }
  .s-rechts { justify-self: end; }
</style>

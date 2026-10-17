<script lang="ts">
  // Durchgehende Player-Leiste am unteren Rand (Rechner) - eigene Optik. Sie
  // zeigt und steuert die Wiedergabe aus PlayerKern; das Audio-Element liegt dort.
  import {
    player, aktuelleSpur, spurWeiter, spurZurueck, playerBeenden, wiederholungWeiter, umschalten, suchenZu,
  } from "./player.svelte";
  import { zumOrdner as zumOrdnerGehen } from "./medien/oeffnen";

  const spur = $derived(aktuelleSpur());
  const stummWirkt = $derived(player.stumm || player.lautstaerke === 0);

  function suche(e: MouseEvent) {
    if (!player.dauer) return;
    const r = (e.currentTarget as HTMLElement).getBoundingClientRect();
    suchenZu(((e.clientX - r.left) / r.width) * player.dauer);
  }
  function mmss(s: number) {
    if (!isFinite(s)) return "0:00";
    const m = Math.floor(s / 60);
    const r = Math.floor(s % 60);
    return `${m}:${r.toString().padStart(2, "0")}`;
  }
  function zumOrdner() {
    if (spur?.pfad) zumOrdnerGehen(spur.pfad, spur.id);
  }
</script>

{#if spur}
  <div class="spieler" role="region" aria-label="Wiedergabe">
    <div class="s-jetzt">
      <div class="s-cover"><i class="fa-solid fa-music"></i></div>
      <div class="s-text">
        <div class="s-titel">{spur.titel}</div>
        {#if player.fehler}
          <div class="s-fehler"><i class="fa-solid fa-triangle-exclamation"></i> {player.fehler}</div>
        {:else if spur.pfad}
          <div class="s-pfad">{spur.pfad.length ? spur.pfad.map((x) => x.name).join(" / ") : "Meine Dateien"}</div>
        {/if}
      </div>
      {#if spur.pfad}<button class="s-mini" title="Zum Ordner" aria-label="Zum Ordner" onclick={zumOrdner}><i class="fa-solid fa-folder-open"></i></button>{/if}
    </div>

    <div class="s-mitte">
      <div class="s-tasten">
        <button class="klein" class:an={player.zufall} aria-label="Zufall" aria-pressed={player.zufall} title="Zufallswiedergabe" onclick={() => (player.zufall = !player.zufall)}><i class="fa-solid fa-shuffle"></i></button>
        <button aria-label="Zurück" onclick={spurZurueck}><i class="fa-solid fa-backward-step"></i></button>
        <button class="gross" aria-label={player.laeuft ? "Pause" : "Abspielen"} onclick={umschalten}>
          {#if player.laden}<i class="fa-solid fa-circle-notch fa-spin"></i>{:else}<i class="fa-solid {player.laeuft ? 'fa-pause' : 'fa-play'}"></i>{/if}
        </button>
        <button aria-label="Weiter" onclick={spurWeiter}><i class="fa-solid fa-forward-step"></i></button>
        <button class="klein wdh" class:an={player.wiederholung !== 'aus'} aria-label="Wiederholen" title={player.wiederholung === 'eine' ? 'Titel wiederholen' : player.wiederholung === 'alle' ? 'Alle wiederholen' : 'Wiederholen aus'} onclick={wiederholungWeiter}>
          <i class="fa-solid fa-repeat"></i>{#if player.wiederholung === 'eine'}<span class="wdh-1">1</span>{/if}
        </button>
      </div>
      <div class="s-fortschritt">
        <span class="s-zeit">{mmss(player.zeit)}</span>
        <div class="s-spur" role="slider" tabindex="0" aria-label="Position" aria-valuenow={Math.floor(player.zeit)} onclick={suche}><div class="s-fuell" style="width:{player.dauer ? (player.zeit / player.dauer) * 100 : 0}%"></div></div>
        <span class="s-zeit">{mmss(player.dauer)}</span>
      </div>
    </div>

    <div class="s-rechts">
      <button class="s-mini" title="Große Ansicht" aria-label="Große Ansicht" onclick={() => (player.voll = true)}><i class="fa-solid fa-chevron-up"></i></button>
      <div class="s-laut">
        <button class="s-mini" aria-label={stummWirkt ? 'Ton an' : 'Stumm'} title={stummWirkt ? 'Ton an' : 'Stumm'} onclick={() => (player.stumm = !player.stumm)}>
          <i class="fa-solid {stummWirkt ? 'fa-volume-xmark' : player.lautstaerke < 0.5 ? 'fa-volume-low' : 'fa-volume-high'}"></i>
        </button>
        <input class="s-laut-regler" type="range" min="0" max="1" step="0.01" bind:value={player.lautstaerke} aria-label="Lautstärke" oninput={() => { if (player.stumm && player.lautstaerke > 0) player.stumm = false; }} />
      </div>
      <button class="s-mini" aria-label="Schließen" title="Schließen" onclick={playerBeenden}><i class="fa-solid fa-xmark"></i></button>
    </div>
  </div>
{/if}

<style>
  /* Eigene, letzte Rasterzeile im .app-Grid - hebt die Ansicht an statt zu überlagern. */
  .spieler { grid-column: 1 / -1; grid-row: 3; height: 78px; display: grid; grid-template-columns: minmax(180px, 1fr) minmax(320px, 1.6fr) minmax(160px, 1fr); align-items: center; gap: var(--a4); padding: 0 var(--a4); background: var(--flaeche); border-top: 1px solid var(--rand); }
  .s-jetzt { display: flex; align-items: center; gap: var(--a3); min-width: 0; }
  .s-cover { width: 48px; height: 48px; border-radius: var(--r2); display: grid; place-items: center; color: #fff; font-size: 1.1rem; flex: none; background: linear-gradient(135deg, #6d5efc, #3b82f6); }
  .s-text { min-width: 0; }
  .s-titel { font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .s-pfad { font-size: 0.78rem; color: var(--text-3); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .s-fehler { font-size: 0.78rem; color: var(--gefahr, #d9534f); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .s-mini { border: none; background: transparent; color: var(--text-2); cursor: pointer; font-size: 0.95rem; padding: 4px; border-radius: var(--r1); }
  .s-mini:hover { color: var(--text); }
  .s-mitte { display: flex; flex-direction: column; align-items: center; gap: 5px; }
  .s-tasten { display: flex; align-items: center; gap: var(--a3); }
  .s-tasten button { border: none; background: transparent; color: var(--text-2); cursor: pointer; font-size: 1rem; width: 34px; height: 34px; border-radius: 50%; display: grid; place-items: center; }
  .s-tasten button:hover { background: var(--flaeche-2); color: var(--text); }
  .s-tasten .klein { width: 30px; height: 30px; font-size: 0.82rem; position: relative; }
  .s-tasten .klein.an { color: var(--akzent); }
  .s-tasten .gross { width: 42px; height: 42px; background: var(--akzent); color: var(--akzent-text); }
  .s-tasten .gross:hover { background: var(--akzent-stark); color: var(--akzent-text); }
  .wdh-1 { position: absolute; bottom: 2px; right: 3px; font-size: 0.5rem; font-weight: 700; line-height: 1; }
  .s-fortschritt { display: flex; align-items: center; gap: var(--a2); width: 100%; max-width: 520px; }
  .s-zeit { font-size: 0.75rem; color: var(--text-3); min-width: 34px; text-align: center; font-variant-numeric: tabular-nums; }
  .s-spur { flex: 1; height: 5px; border-radius: 3px; background: var(--flaeche-3); position: relative; cursor: pointer; }
  .s-fuell { position: absolute; left: 0; top: 0; bottom: 0; background: var(--akzent); border-radius: 3px; }
  .s-rechts { justify-self: end; display: flex; align-items: center; gap: var(--a2); min-width: 0; }
  .s-laut { display: flex; align-items: center; gap: 4px; }
  .s-laut-regler { width: 76px; max-width: 22vw; accent-color: var(--akzent); cursor: pointer; }
</style>

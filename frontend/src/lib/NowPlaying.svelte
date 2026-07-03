<script lang="ts">
  // Ausgeklappte Wiedergabe-Ansicht. Steuert denselben globalen Player wie die
  // Leiste (Steuerfunktionen im Store, ein gemeinsames Audio-Element).
  import {
    player, aktuelleSpur, spurWeiter, spurZurueck, wiederholungWeiter,
    umschalten, suchenZu, springen, setzeTempo, springeZuIndex,
  } from "./player.svelte";
  import { haupt } from "./zustand.svelte";
  import { waehleApp } from "../plugins/appzustand.svelte";

  const spur = $derived(aktuelleSpur());
  const TEMPI = [0.5, 0.75, 1, 1.25, 1.5, 2];

  function mmss(s: number) { if (!isFinite(s)) return "0:00"; const m = Math.floor(s / 60); const r = Math.floor(s % 60); return `${m}:${r.toString().padStart(2, "0")}`; }
  function pfadText(p: { id: string; name: string }[] | null) { return !p || !p.length ? "Meine Dateien" : p.map((x) => x.name).join(" / "); }
  function suche(e: MouseEvent) { if (!player.dauer) return; const r = (e.currentTarget as HTMLElement).getBoundingClientRect(); suchenZu(((e.clientX - r.left) / r.width) * player.dauer); }
  function zumOrdner() { if (!spur?.pfad) return; haupt.oeffnePfad(spur.pfad, spur.id); waehleApp("dateien"); player.voll = false; }
  function tempoName(t: number) { return (t === 1 ? "1" : t.toString().replace(".", ",")) + "x"; }
  function taste(e: KeyboardEvent) { if (e.key === "Escape") player.voll = false; }
</script>

<svelte:window onkeydown={taste} />

{#if spur}
  <div class="jv" role="dialog" aria-modal="true" aria-label="Aktuelle Wiedergabe">
    <div class="jv-panel">
      <div class="jv-kopf">
        <button class="jv-min" title="Einklappen" aria-label="Einklappen" onclick={() => (player.voll = false)}><i class="fa-solid fa-chevron-down"></i></button>
        <span class="jv-titelzeile">Aktuelle Wiedergabe</span>
        <span class="jv-luecke"></span>
      </div>
      <div class="jv-body">
        <div class="jv-haupt">
          <div class="jv-cover"><i class="fa-solid fa-music"></i></div>
          <div class="jv-titel">{spur.titel}</div>
          {#if spur.pfad}<button class="jv-sub" title="Zum Ordner" onclick={zumOrdner}>{pfadText(spur.pfad)}</button>{/if}
          <div class="jv-fortschritt">
            <span class="jv-zeit">{mmss(player.zeit)}</span>
            <div class="jv-spur" role="slider" tabindex="0" aria-label="Position" aria-valuenow={Math.floor(player.zeit)} onclick={suche}><div class="jv-fuell" style="width:{player.dauer ? (player.zeit / player.dauer) * 100 : 0}%"></div></div>
            <span class="jv-zeit">{mmss(player.dauer)}</span>
          </div>
          <div class="jv-transport">
            <button class:an={player.zufall} title="Zufall" aria-label="Zufall" onclick={() => (player.zufall = !player.zufall)}><i class="fa-solid fa-shuffle"></i></button>
            <button title="Zurück" aria-label="Zurück" onclick={spurZurueck}><i class="fa-solid fa-backward-step"></i></button>
            <button class="skip" title="30 Sekunden zurück" aria-label="30 Sekunden zurück" onclick={() => springen(-30)}><i class="fa-solid fa-rotate-left"></i><b>30</b></button>
            <button class="gross" title={player.laeuft ? "Pause" : "Abspielen"} aria-label={player.laeuft ? "Pause" : "Abspielen"} onclick={umschalten}><i class="fa-solid {player.laeuft ? 'fa-pause' : 'fa-play'}"></i></button>
            <button class="skip" title="30 Sekunden vor" aria-label="30 Sekunden vor" onclick={() => springen(30)}><i class="fa-solid fa-rotate-right"></i><b>30</b></button>
            <button title="Weiter" aria-label="Weiter" onclick={spurWeiter}><i class="fa-solid fa-forward-step"></i></button>
            <button class:an={player.wiederholung !== 'aus'} title="Wiederholen" aria-label="Wiederholen" onclick={wiederholungWeiter}><i class="fa-solid fa-repeat"></i>{#if player.wiederholung === 'eine'}<b class="w1">1</b>{/if}</button>
          </div>
          <div class="jv-tempo">
            <span class="jv-tempo-l">Tempo</span>
            {#each TEMPI as t}<button class:an={player.tempo === t} onclick={() => setzeTempo(t)}>{tempoName(t)}</button>{/each}
          </div>
        </div>
        <aside class="jv-schlange">
          <div class="jv-schlange-kopf"><i class="fa-solid fa-list-ol"></i> Als Nächstes</div>
          <ul>
            {#each player.liste as s, i (s.id + "-" + i)}
              <li class:jetzt={i === player.index}>
                <button class="js-z" onclick={() => springeZuIndex(i)}>
                  <span class="js-num">{#if i === player.index}<i class="fa-solid fa-volume-high"></i>{:else}{i + 1}{/if}</span>
                  <span class="js-t"><b>{s.titel}</b>{#if s.pfad}<small>{pfadText(s.pfad)}</small>{/if}</span>
                </button>
              </li>
            {/each}
          </ul>
        </aside>
      </div>
    </div>
  </div>
{/if}

<style>
  .jv { position: fixed; inset: 0; z-index: 70; background: var(--flaeche); }
  .jv-panel { height: 100%; max-width: 1080px; margin: 0 auto; display: flex; flex-direction: column; padding: 0 var(--a5); }
  .jv-kopf { display: flex; align-items: center; justify-content: space-between; padding: var(--a3) 0; }
  .jv-min { border: none; background: var(--flaeche-2); color: var(--text-2); width: 36px; height: 36px; border-radius: 50%; cursor: pointer; }
  .jv-min:hover { color: var(--text); }
  .jv-luecke { width: 36px; }
  .jv-titelzeile { color: var(--text-3); font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.06em; }
  .jv-body { flex: 1; display: grid; grid-template-columns: 1.4fr 1fr; gap: var(--a5); align-items: center; padding-bottom: var(--a5); min-height: 0; }
  .jv-haupt { display: flex; flex-direction: column; align-items: center; text-align: center; gap: var(--a3); }
  .jv-cover { width: min(300px, 36vh); aspect-ratio: 1; border-radius: var(--r3); display: grid; place-items: center; color: #fff; font-size: 3.4rem; background: linear-gradient(135deg, #6d5efc, #3b82f6); }
  .jv-titel { font-size: 1.35rem; font-weight: 700; max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .jv-sub { border: none; background: transparent; color: var(--text-3); cursor: pointer; font: inherit; margin-top: -6px; }
  .jv-sub:hover { color: var(--akzent); }
  .jv-fortschritt { display: flex; align-items: center; gap: var(--a2); width: 100%; max-width: 440px; }
  .jv-zeit { font-size: 0.78rem; color: var(--text-3); min-width: 36px; font-variant-numeric: tabular-nums; }
  .jv-spur { flex: 1; height: 6px; border-radius: 3px; background: var(--flaeche-3); position: relative; cursor: pointer; }
  .jv-fuell { position: absolute; top: 0; bottom: 0; left: 0; background: var(--akzent); border-radius: 3px; }
  .jv-transport { display: flex; align-items: center; gap: var(--a3); }
  .jv-transport button { border: none; background: transparent; color: var(--text-2); cursor: pointer; font-size: 1.1rem; width: 42px; height: 42px; border-radius: 50%; display: grid; place-items: center; position: relative; }
  .jv-transport button:hover { background: var(--flaeche-2); color: var(--text); }
  .jv-transport .an { color: var(--akzent); }
  .jv-transport .gross { width: 58px; height: 58px; font-size: 1.4rem; background: var(--akzent); color: var(--akzent-text); }
  .jv-transport .gross:hover { background: var(--akzent-stark); color: var(--akzent-text); }
  .jv-transport .skip i { font-size: 1.35rem; }
  .jv-transport .skip b { position: absolute; top: 52%; left: 50%; transform: translate(-50%, -50%); font-size: 0.5rem; font-weight: 700; }
  .jv-transport .w1 { position: absolute; bottom: 4px; right: 6px; font-size: 0.52rem; font-weight: 700; }
  .jv-tempo { display: flex; align-items: center; gap: 5px; flex-wrap: wrap; justify-content: center; }
  .jv-tempo-l { color: var(--text-3); font-size: 0.8rem; margin-right: var(--a1); }
  .jv-tempo button { border: 1px solid var(--rand); background: var(--flaeche-2); color: var(--text-2); border-radius: 999px; padding: 3px 11px; font-size: 0.78rem; cursor: pointer; }
  .jv-tempo button.an { background: var(--akzent-weich); color: var(--akzent-stark); border-color: transparent; font-weight: 600; }
  .jv-schlange { align-self: stretch; display: flex; flex-direction: column; min-height: 0; background: var(--flaeche-2); border: 1px solid var(--rand); border-radius: var(--r3); padding: var(--a3); }
  .jv-schlange-kopf { font-weight: 600; margin-bottom: var(--a2); display: flex; align-items: center; gap: var(--a2); }
  .jv-schlange ul { list-style: none; margin: 0; padding: 0; overflow-y: auto; display: flex; flex-direction: column; gap: 2px; }
  .jv-schlange li { border-radius: var(--r2); }
  .jv-schlange li.jetzt { background: var(--akzent-weich); }
  .js-z { width: 100%; display: flex; align-items: center; gap: var(--a2); padding: var(--a2); border: none; background: transparent; cursor: pointer; text-align: left; color: var(--text); font: inherit; border-radius: var(--r2); }
  .js-z:hover { background: var(--flaeche-3); }
  .jv-schlange li.jetzt .js-z:hover { background: var(--akzent-weich); }
  .js-num { width: 24px; text-align: center; color: var(--text-3); font-size: 0.85rem; flex: none; }
  .jv-schlange li.jetzt .js-num { color: var(--akzent); }
  .js-t { flex: 1; min-width: 0; display: flex; flex-direction: column; overflow: hidden; }
  .js-t small { color: var(--text-3); font-size: 0.72rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .js-t b { font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  @media (max-width: 720px) {
    .jv-body { grid-template-columns: 1fr; overflow-y: auto; align-content: start; }
  }
</style>

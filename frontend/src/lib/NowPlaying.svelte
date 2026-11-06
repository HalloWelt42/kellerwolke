<script lang="ts">
  // Ausgeklappte Wiedergabe-Ansicht (Entwurf mockups/wiedergabe.html, KW-8): die Titelliste im Vordergrund, nur drei
  // Tempi, und die Liste folgt dem laufenden Titel (er steht markiert in der Mitte). Steuert denselben globalen Player
  // wie die Leiste (Steuerfunktionen im Store, ein gemeinsames Audio-Element). Am Rechner Steuerung links und Liste
  // rechts, am Telefon das Cover klein neben dem Titel und darunter alles für die Liste.
  import { tick } from "svelte";
  import {
    player, aktuelleSpur, spurWeiter, spurZurueck, wiederholungWeiter,
    umschalten, suchenZu, springen, setzeTempo, springeZuIndex, TEMPI,
  } from "./player.svelte";
  import { zumOrdner as zumOrdnerGehen } from "./medien/oeffnen";
  import Dauer from "./medien/Dauer.svelte";

  const spur = $derived(aktuelleSpur());

  function mmss(s: number) { if (!isFinite(s)) return "0:00"; const m = Math.floor(s / 60); const r = Math.floor(s % 60); return `${m}:${r.toString().padStart(2, "0")}`; }
  function pfadText(p: { name: string }[] | null) { return !p || !p.length ? "Meine Dateien" : p.map((x) => x.name).join(" / "); }
  function suche(e: MouseEvent) { if (!player.dauer) return; const r = (e.currentTarget as HTMLElement).getBoundingClientRect(); suchenZu(((e.clientX - r.left) / r.width) * player.dauer); }
  function zumOrdner() { if (!spur?.pfad) return; zumOrdnerGehen(spur.pfad, spur.id); player.voll = false; }
  function tempoName(t: number) { return (t === 1 ? "1" : t.toString().replace(".", ",")) + "x"; }
  function taste(e: KeyboardEvent) { if (e.key === "Escape") player.voll = false; }

  // Die Liste folgt dem Titel: nach jedem Titelwechsel steht der laufende in der Mitte. Beim Öffnen sofort, danach
  // gleitend; gerollt wird erst nach dem Aufbau, sonst stimmt die Lage nicht.
  let liste = $state<HTMLOListElement | null>(null);
  let erstes = true;
  $effect(() => {
    const i = player.index;
    const el = liste;
    if (!el || i < 0) return;
    void tick().then(() =>
      requestAnimationFrame(() => {
        const li = el.children[i] as HTMLElement | undefined;
        if (!li) return;
        el.scrollTo({ top: li.offsetTop - el.offsetTop - el.clientHeight / 2 + li.clientHeight / 2, behavior: erstes ? "auto" : "smooth" });
        erstes = false;
      }),
    );
  });
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
          <div class="jv-kennung">
            <div class="jv-cover"><i class="fa-solid fa-music"></i></div>
            <div class="jv-text">
              <div class="jv-titel">{spur.titel}</div>
              {#if spur.pfad}<button class="jv-sub" title="Zum Ordner" onclick={zumOrdner}>{pfadText(spur.pfad)}</button>{/if}
            </div>
          </div>
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
          <div class="jv-tempo" role="radiogroup" aria-label="Tempo">
            {#each TEMPI as t (t)}
              <button role="radio" aria-checked={player.tempo === t} class:an={player.tempo === t} onclick={() => setzeTempo(t)}>{tempoName(t)}</button>
            {/each}
          </div>
        </div>
        <section class="jv-schlange" aria-label="Titelliste">
          <div class="jv-schlange-kopf">
            <i class="fa-solid fa-list-ol"></i> Titelliste
            <span class="jv-stand">{player.index + 1} von {player.liste.length}</span>
          </div>
          <ol bind:this={liste}>
            {#each player.liste as s, i (s.id + "-" + i)}
              <li class:jetzt={i === player.index} class:gespielt={i < player.index}>
                <button class="js-z" onclick={() => springeZuIndex(i)} aria-current={i === player.index ? "true" : undefined}>
                  <span class="js-num">{#if i === player.index}<i class="fa-solid {player.laeuft ? 'fa-volume-high' : 'fa-pause'}"></i>{:else}{i + 1}{/if}</span>
                  <span class="js-t"><b>{s.titel}</b>{#if s.pfad}<small>{pfadText(s.pfad)}</small>{/if}</span>
                  <span class="js-dauer"><Dauer m={s} art="audio" leer="" /></span>
                </button>
              </li>
            {/each}
          </ol>
        </section>
      </div>
    </div>
  </div>
{/if}

<style>
  .jv { position: fixed; inset: 0; z-index: 70; background: var(--flaeche); }
  .jv-panel { height: 100%; max-width: 1180px; margin: 0 auto; display: flex; flex-direction: column; padding: 0 var(--a5); }
  .jv-kopf { display: flex; align-items: center; justify-content: space-between; padding: var(--a3) 0; flex: none; }
  .jv-min { border: none; background: var(--flaeche-2); color: var(--text-2); width: 36px; height: 36px; border-radius: 50%; cursor: pointer; }
  .jv-min:hover { color: var(--text); }
  .jv-luecke { width: 36px; }
  .jv-titelzeile { color: var(--text-3); font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.06em; }
  /* minmax(0, ...): eine Spalte "1fr" wird nie schmaler als ihr breitester Inhalt (KW-6). Die Liste bekommt den
     größeren Teil (KW-8). */
  .jv-body { flex: 1; min-height: 0; display: grid; grid-template-columns: minmax(0, 0.8fr) minmax(0, 1.4fr); gap: var(--a5); padding-bottom: var(--a5); }
  .jv-haupt { display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; gap: var(--a3); min-width: 0; }
  .jv-kennung { display: flex; flex-direction: column; align-items: center; gap: var(--a3); width: 100%; min-width: 0; }
  .jv-text { width: 100%; min-width: 0; display: flex; flex-direction: column; align-items: center; }
  .jv-cover { width: min(200px, 30vh); aspect-ratio: 1; border-radius: var(--r3); display: grid; place-items: center; color: #fff; font-size: 2.6rem; background: linear-gradient(135deg, #6d5efc, #3b82f6); flex: none; }
  .jv-titel { font-size: 1.25rem; font-weight: 700; max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .jv-sub { border: none; background: transparent; color: var(--text-3); cursor: pointer; font: inherit; padding: 0; max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .jv-sub:hover { color: var(--akzent); }
  .jv-fortschritt { display: flex; align-items: center; gap: var(--a2); width: 100%; max-width: 420px; }
  .jv-zeit { font-size: 0.78rem; color: var(--text-3); min-width: 36px; font-variant-numeric: tabular-nums; }
  .jv-spur { flex: 1; height: 6px; border-radius: 3px; background: var(--flaeche-3); position: relative; cursor: pointer; }
  .jv-fuell { position: absolute; top: 0; bottom: 0; left: 0; background: var(--akzent); border-radius: 3px; }
  .jv-transport { display: flex; align-items: center; justify-content: space-between; width: 100%; max-width: 380px; }
  .jv-transport button { border: none; background: transparent; color: var(--text-2); cursor: pointer; font-size: 1.1rem; width: 40px; height: 40px; border-radius: 50%; display: grid; place-items: center; position: relative; }
  .jv-transport button:hover { background: var(--flaeche-2); color: var(--text); }
  .jv-transport .an { color: var(--akzent); }
  .jv-transport .gross { width: 56px; height: 56px; font-size: 1.35rem; background: var(--akzent); color: var(--akzent-text); }
  .jv-transport .gross:hover { background: var(--akzent-stark); color: var(--akzent-text); }
  .jv-transport .skip i { font-size: 1.35rem; }
  .jv-transport .skip b { position: absolute; top: 52%; left: 50%; transform: translate(-50%, -50%); font-size: 0.5rem; font-weight: 700; }
  .jv-transport .w1 { position: absolute; bottom: 4px; right: 6px; font-size: 0.52rem; font-weight: 700; }
  /* Drei Tempi als Knopfleiste: genau eines ist aktiv */
  .jv-tempo { display: inline-flex; gap: 2px; background: var(--flaeche-2); border: 1px solid var(--rand); border-radius: var(--r2); padding: 2px; }
  .jv-tempo button { border: none; background: transparent; color: var(--text-2); font: inherit; font-size: 0.85rem; min-width: 56px; height: 32px; border-radius: var(--r1); cursor: pointer; font-variant-numeric: tabular-nums; }
  .jv-tempo button:hover { color: var(--text); }
  .jv-tempo button.an { background: var(--akzent-weich); color: var(--akzent-stark); font-weight: 600; }

  /* Die Titelliste: rollt selbst, folgt dem laufenden Titel */
  .jv-schlange { display: flex; flex-direction: column; min-height: 0; min-width: 0; background: var(--flaeche-2); border: 1px solid var(--rand); border-radius: var(--r3); }
  .jv-schlange-kopf { font-weight: 600; padding: var(--a3) var(--a3) var(--a2); display: flex; align-items: center; gap: var(--a2); flex: none; }
  .jv-stand { margin-left: auto; color: var(--text-3); font-weight: 400; font-size: 0.85rem; font-variant-numeric: tabular-nums; }
  .jv-schlange ol { list-style: none; margin: 0; padding: 0 6px 6px; overflow-y: auto; min-height: 0; display: flex; flex-direction: column; gap: 2px; }
  .jv-schlange li { border-radius: var(--r2); }
  .jv-schlange li.gespielt { opacity: 0.55; }
  .jv-schlange li.jetzt { background: var(--akzent-weich); box-shadow: inset 3px 0 0 var(--akzent); border-radius: 0 var(--r2) var(--r2) 0; }
  .js-z { width: 100%; display: flex; align-items: center; gap: var(--a2); padding: var(--a2); border: none; background: transparent; cursor: pointer; text-align: left; color: var(--text); font: inherit; border-radius: var(--r2); }
  .js-z:hover { background: var(--flaeche-3); }
  .jv-schlange li.jetzt .js-z:hover { background: var(--akzent-weich); }
  .js-num { width: 26px; text-align: center; color: var(--text-3); font-size: 0.85rem; flex: none; font-variant-numeric: tabular-nums; }
  .jv-schlange li.jetzt .js-num, .jv-schlange li.jetzt .js-t b { color: var(--akzent-stark); font-weight: 600; }
  .js-t { flex: 1; min-width: 0; display: flex; flex-direction: column; overflow: hidden; }
  .js-t small { color: var(--text-3); font-size: 0.72rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .js-t b { font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .js-dauer { color: var(--text-3); font-size: 0.82rem; font-variant-numeric: tabular-nums; flex: none; }

  /* Telefon: Cover klein neben dem Titel, darunter Steuerung, der Rest ist Liste */
  @media (max-width: 720px) {
    .jv-panel { padding: 0 var(--a4); }
    .jv-body { display: flex; flex-direction: column; gap: var(--a3); padding-bottom: var(--a4); }
    .jv-haupt { flex: none; gap: var(--a2); }
    .jv-kennung { flex-direction: row; text-align: left; }
    .jv-cover { width: 64px; font-size: 1.5rem; border-radius: var(--r2); }
    .jv-text { align-items: flex-start; }
    .jv-titel { font-size: 1.05rem; }
    .jv-fortschritt { max-width: none; }
    /* Sieben Knöpfe passen auch auf 320 Pixel */
    .jv-transport { max-width: 440px; }
    .jv-transport button { width: 38px; height: 38px; }
    .jv-transport .gross { width: 54px; height: 54px; }
    .jv-schlange { flex: 1; }
  }
</style>

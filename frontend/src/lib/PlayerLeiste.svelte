<script lang="ts">
  // Durchgehende Player-Leiste am unteren Rand - eigene Optik (kein natives
  // <audio controls>). Wird einmalig von App.svelte gerendert und ueberlebt so
  // jede Navigation.
  import { onMount } from "svelte";
  import {
    player, aktuelleSpur, spurWeiter, spurZurueck, playerBeenden,
    beiEnde, wiederholungWeiter, zustandLaden, zustandSpeichern,
    audioElement, umschalten, springen,
  } from "./player.svelte";
  import NowPlaying from "./NowPlaying.svelte";
  import { haupt } from "./zustand.svelte";
  import { waehleApp } from "../plugins/appzustand.svelte";

  let audioEl: HTMLAudioElement;
  let geladeneUrl = "";
  let laden = $state(false); // puffert gerade
  let fehler = $state(""); // z.B. Format nicht abspielbar
  const spur = $derived(aktuelleSpur());

  // Reload-Persistenz synchron beim Init einlesen (vor dem ersten Effekt).
  let startSekunde = zustandLaden();
  let autoAbspielen = player.index < 0; // wiederhergestellte Spur NICHT automatisch starten

  // Nur bei echtem Spurwechsel neu laden. Wiederhergestellte erste Spur nicht auto.
  $effect(() => {
    const s = spur;
    if (!audioEl) return;
    if (s && s.url !== geladeneUrl) {
      geladeneUrl = s.url;
      fehler = "";
      audioEl.src = s.url;
      if (autoAbspielen) audioEl.play().catch(() => {});
      autoAbspielen = true;
    } else if (!s) {
      geladeneUrl = "";
      audioEl.pause();
      audioEl.removeAttribute("src");
    }
  });

  // Lautstaerke/Stumm auf das Element spiegeln.
  $effect(() => {
    if (audioEl) {
      audioEl.volume = player.lautstaerke;
      audioEl.muted = player.stumm;
    }
  });

  // Tempo auf das Element spiegeln.
  $effect(() => {
    if (audioEl) audioEl.playbackRate = player.tempo;
  });

  // Media Session: Titel + Wiedergabestatus.
  $effect(() => {
    const s = spur;
    if (!("mediaSession" in navigator)) return;
    if (s) {
      navigator.mediaSession.metadata = new MediaMetadata({
        title: s.titel,
        artist: s.pfad && s.pfad.length ? s.pfad.map((x) => x.name).join(" / ") : "Kellerwolke",
      });
      navigator.mediaSession.playbackState = player.laeuft ? "playing" : "paused";
    } else {
      navigator.mediaSession.metadata = null;
    }
  });

  // Strukturzustand sichern, sobald er sich aendert (Position kommt zusaetzlich
  // beim Verlassen der Seite dazu - kein Speichern im Sekundentakt).
  $effect(() => {
    player.index;
    player.liste;
    player.wiederholung;
    player.zufall;
    zustandSpeichern();
  });

  onMount(() => {
    audioElement(audioEl);
    const sichern = () => zustandSpeichern();
    window.addEventListener("beforeunload", sichern);
    // Media Session: Betriebssystem-/Kopfhoerer-/Sperrbildschirm-Steuerung.
    if ("mediaSession" in navigator) {
      const ms = navigator.mediaSession;
      ms.setActionHandler("play", () => umschalten());
      ms.setActionHandler("pause", () => umschalten());
      ms.setActionHandler("previoustrack", () => spurZurueck());
      ms.setActionHandler("nexttrack", () => spurWeiter());
      ms.setActionHandler("seekbackward", () => springen(-10));
      ms.setActionHandler("seekforward", () => springen(10));
    }
    return () => {
      window.removeEventListener("beforeunload", sichern);
      audioElement(null);
    };
  });

  function toggle() {
    if (!audioEl) return;
    if (audioEl.paused) audioEl.play().catch(() => {});
    else audioEl.pause();
  }
  function suche(e: MouseEvent) {
    if (!audioEl || !player.dauer) return;
    const r = (e.currentTarget as HTMLElement).getBoundingClientRect();
    audioEl.currentTime = ((e.clientX - r.left) / r.width) * player.dauer;
  }
  function mmss(s: number) {
    if (!isFinite(s)) return "0:00";
    const m = Math.floor(s / 60);
    const r = Math.floor(s % 60);
    return `${m}:${r.toString().padStart(2, "0")}`;
  }
  function zumOrdner() {
    if (!spur?.pfad) return;
    haupt.oeffnePfad(spur.pfad, spur.id);
    waehleApp("dateien");
  }
  function amEnde() {
    const was = beiEnde();
    if (was === "wiederhole") {
      if (audioEl) {
        audioEl.currentTime = 0;
        audioEl.play().catch(() => {});
      }
    } else if (was === "stopp") {
      player.laeuft = false;
    }
    // "weiter": Index wurde geaendert -> der Lade-Effekt spielt die naechste Spur
  }
  function beiMetadaten() {
    player.dauer = audioEl.duration;
    fehler = "";
    if (startSekunde > 0 && startSekunde < audioEl.duration) audioEl.currentTime = startSekunde;
    startSekunde = 0;
  }

  const stummWirkt = $derived(player.stumm || player.lautstaerke === 0);

  // Tastatur: nur wenn eine Spur aktiv ist und der Fokus NICHT in einem Eingabefeld
  // sitzt. Bewusst nur Leertaste (Play/Pause) und m (Stumm) - Pfeile bleiben den
  // Ansichten (z.B. Bild-Lightbox); Seek/Sprung kommt in die Now-Playing-Ansicht.
  function tastatur(e: KeyboardEvent) {
    if (!spur) return;
    const z = e.target as HTMLElement | null;
    if (z && (z.tagName === "INPUT" || z.tagName === "TEXTAREA" || z.tagName === "SELECT" || z.isContentEditable)) return;
    if (e.key === " ") {
      e.preventDefault();
      toggle();
    } else if (e.key === "m" || e.key === "M") {
      player.stumm = !player.stumm;
    }
  }
</script>

<svelte:window onkeydown={tastatur} />

<audio
  bind:this={audioEl}
  onplay={() => { player.laeuft = true; fehler = ""; }}
  onpause={() => (player.laeuft = false)}
  ontimeupdate={() => (player.zeit = audioEl.currentTime)}
  onloadedmetadata={beiMetadaten}
  onwaiting={() => (laden = true)}
  onplaying={() => { laden = false; fehler = ""; }}
  oncanplay={() => (laden = false)}
  onerror={() => { laden = false; fehler = "Format wird hier nicht unterstützt"; player.laeuft = false; }}
  onended={amEnde}
></audio>

{#if spur}
  <div class="spieler" role="region" aria-label="Wiedergabe">
    <div class="s-jetzt">
      <div class="s-cover"><i class="fa-solid fa-music"></i></div>
      <div class="s-text">
        <div class="s-titel">{spur.titel}</div>
        {#if fehler}
          <div class="s-fehler"><i class="fa-solid fa-triangle-exclamation"></i> {fehler}</div>
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
        <button class="gross" aria-label={player.laeuft ? "Pause" : "Abspielen"} onclick={toggle}>
          {#if laden}<i class="fa-solid fa-circle-notch fa-spin"></i>{:else}<i class="fa-solid {player.laeuft ? 'fa-pause' : 'fa-play'}"></i>{/if}
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

{#if player.voll}
  <NowPlaying />
{/if}

<style>
  audio { display: none; }
  /* Eigene, letzte Rasterzeile im .app-Grid - hebt die Ansicht an statt zu ueberlagern. */
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

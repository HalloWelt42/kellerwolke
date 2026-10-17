<script lang="ts">
  // Die Wiedergabe selbst: das eine Audio-Element mit Laden, Fortschritt, Ende,
  // Media Session und Tasten. Einmal in App.svelte, ohne eigene Optik; Leiste
  // (Rechner) und Mini-Spieler (Telefon) zeigen und steuern nur.
  import { onMount } from "svelte";
  import {
    player, aktuelleSpur, spurWeiter, spurZurueck, playerBeenden,
    beiEnde, wiederholungWeiter, zustandLaden, zustandSpeichern,
    audioElement, umschalten, springen, spurUrl,
  } from "./player.svelte";
  import NowPlaying from "./NowPlaying.svelte";
  import { ursache } from "./medien/adressen";
  import { vollansichtOffen } from "./vorschau.svelte";
  import { auth } from "./auth.svelte";

  let audioEl: HTMLAudioElement;
  let geladeneUrl = "";
  const spur = $derived(aktuelleSpur());

  // Reload-Persistenz synchron beim Init einlesen (vor dem ersten Effekt).
  let startSekunde = zustandLaden(auth.benutzer?.id ?? "");
  let autoAbspielen = player.index < 0; // wiederhergestellte Spur NICHT automatisch starten

  // Nur bei echtem Spurwechsel neu laden. Wiederhergestellte erste Spur nicht auto.
  $effect(() => {
    const s = spur;
    if (!audioEl) return;
    const url = s ? spurUrl(s) : "";
    if (s && url !== geladeneUrl) {
      geladeneUrl = url;
      player.fehler = "";
      audioEl.src = url;
      if (autoAbspielen) audioEl.play().catch(() => {});
      autoAbspielen = true;
    } else if (!s) {
      geladeneUrl = "";
      audioEl.pause();
      audioEl.removeAttribute("src");
    }
  });

  // Lautstärke/Stumm auf das Element spiegeln.
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

  // Strukturzustand sichern, sobald er sich ändert (Position kommt zusätzlich
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
    // Media Session: Betriebssystem-/Kopfhörer-/Sperrbildschirm-Steuerung.
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

  async function beiFehler() {
    player.laden = false;
    player.laeuft = false;
    player.fehler = await ursache(geladeneUrl);
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
    // "weiter": Index wurde geändert -> der Lade-Effekt spielt die nächste Spur
  }
  function beiMetadaten() {
    player.dauer = audioEl.duration;
    player.fehler = "";
    if (startSekunde > 0 && startSekunde < audioEl.duration) audioEl.currentTime = startSekunde;
    startSekunde = 0;
  }


  // Tastatur: nur wenn eine Spur aktiv ist und der Fokus NICHT in einem Eingabefeld
  // sitzt. Bewusst nur Leertaste (Play/Pause) und m (Stumm) - Pfeile bleiben den
  // Ansichten (z.B. Bild-Lightbox); Seek/Sprung kommt in die Now-Playing-Ansicht.
  function tastatur(e: KeyboardEvent) {
    if (!spur || vollansichtOffen()) return; // die offene Vollansicht hat Vorrang
    const z = e.target as HTMLElement | null;
    if (z && (z.tagName === "INPUT" || z.tagName === "TEXTAREA" || z.tagName === "SELECT" || z.isContentEditable)) return;
    if (e.key === " ") {
      e.preventDefault();
      umschalten();
    } else if (e.key === "m" || e.key === "M") {
      player.stumm = !player.stumm;
    }
  }
</script>

<svelte:window onkeydown={tastatur} />

<audio
  bind:this={audioEl}
  onplay={() => { player.laeuft = true; player.fehler = ""; }}
  onpause={() => (player.laeuft = false)}
  ontimeupdate={() => (player.zeit = audioEl.currentTime)}
  onloadedmetadata={beiMetadaten}
  onwaiting={() => (player.laden = true)}
  onplaying={() => { player.laden = false; player.fehler = ""; }}
  oncanplay={() => (player.laden = false)}
  onerror={beiFehler}
  onended={amEnde}
></audio>

{#if player.voll}
  <NowPlaying />
{/if}

<style>
  audio { display: none; }
</style>

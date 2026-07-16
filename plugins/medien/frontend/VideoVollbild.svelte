<script lang="ts">
  import type { Browser } from "../../lib/browser.svelte";
  import { streamUrl } from "./medien";
  import { player, umschalten } from "../../lib/player.svelte";

  // Vollansicht eines Videos: der Browser spielt direkt vom Stream-Endpunkt und
  // holt sich per HTTP-Range nur die Ausschnitte, die er gerade braucht -
  // deshalb ist Spulen billig, auch bei einer 1-GB-Datei.
  //
  // Absichtlich nur id und name verlangt: so passt sowohl der Knoten aus der
  // Datei-Faehigkeit als auch der Listeneintrag der Medien-Ansicht hinein,
  // ohne Umbau oder Typ-Trickserei.
  interface Props {
    knoten: { id: string; name: string };
    browser?: Browser;
    schliessen: () => void;
  }
  let { knoten, schliessen }: Props = $props();

  let fehler = $state(false);

  // Zwei Tonquellen gleichzeitig waeren unangenehm: laufende Audiowiedergabe in
  // der Player-Leiste anhalten, sobald ein Video geoeffnet wird.
  $effect(() => {
    void knoten.id;
    if (player.laeuft) umschalten(); // pausiert das laufende Audio
  });

  function taste(e: KeyboardEvent) {
    if (e.key === "Escape") schliessen();
  }
</script>

<svelte:window onkeydown={taste} />

<div class="vf-huelle" role="presentation" onclick={schliessen}>
  <!-- svelte-ignore a11y_media_has_caption -->
  <video
    class="vf-video"
    src={streamUrl(knoten.id)}
    controls
    autoplay
    playsinline
    onerror={() => (fehler = true)}
    onclick={(e) => e.stopPropagation()}
  ></video>

  {#if fehler}
    <div class="vf-fehler" role="presentation" onclick={(e) => e.stopPropagation()}>
      <i class="fa-solid fa-triangle-exclamation"></i>
      <span>Dieses Video kann der Browser nicht abspielen.</span>
      <span class="vf-hinweis">
        Der Inhalt liegt unversehrt in der Wolke - es fehlt nur der passende Codec
        im Browser. Sicher gehen mp4 (H.264) und webm.
      </span>
    </div>
  {/if}

  <div class="vf-leiste" role="presentation" onclick={(e) => e.stopPropagation()}>
    <span class="vf-name">{knoten.name}</span>
    <button class="vf-knopf" title="Schließen" aria-label="Schließen" onclick={schliessen}>
      <i class="fa-solid fa-xmark"></i>
    </button>
  </div>
</div>

<style>
  .vf-huelle {
    position: fixed; inset: 0; background: rgba(0, 0, 0, 0.94);
    display: flex; align-items: center; justify-content: center; z-index: 70;
  }
  .vf-video { max-width: 94vw; max-height: 84vh; background: #000; outline: none; }
  .vf-leiste {
    position: absolute; top: var(--a4); left: 50%; transform: translateX(-50%);
    display: flex; align-items: center; gap: var(--a2);
    background: rgba(20, 20, 24, 0.9); border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: var(--r3); padding: var(--a2) var(--a3); color: #fff; max-width: 80vw;
  }
  .vf-name {
    max-width: 60vw; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    font-size: 0.86rem;
  }
  .vf-knopf {
    border: none; background: transparent; color: #fff; cursor: pointer;
    font-size: 1rem; width: 32px; height: 32px; border-radius: var(--r1); flex: none;
  }
  .vf-knopf:hover { background: rgba(255, 255, 255, 0.14); }
  .vf-fehler {
    position: absolute; display: flex; flex-direction: column; align-items: center;
    gap: var(--a2); color: #fff; font-size: 0.9rem; text-align: center;
    max-width: 420px; padding: var(--a4);
  }
  .vf-fehler i { font-size: 2rem; color: #fbbf24; }
  .vf-hinweis { font-size: 0.78rem; color: rgba(255, 255, 255, 0.7); }
</style>

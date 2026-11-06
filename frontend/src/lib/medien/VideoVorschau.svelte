<script lang="ts">
  import { formatKuerzel, vorschauUrl } from "./adressen";

  // Standbild eines Videos mit Abspielzeichen; ohne Standbild (kein ffmpeg) das Film-Symbol. Mit `abspielen` ist das
  // Zeichen ein Knopf (Kacheln, KW-5), sonst zeigt es nur und geöffnet wird über die Ansicht (Doppelklick, Detail).
  interface Props {
    m: { id: string; etag: string | null; name: string };
    abspielen?: () => void;
  }
  let { m, abspielen }: Props = $props();
  let kaputt = $state(false);
  $effect(() => {
    void m.id;
    void m.etag;
    kaputt = false;
  });
</script>

<div class="vv-cover" class:ohne-bild={kaputt}>
  {#if kaputt}
    <i class="vv-film fa-solid fa-film"></i>
  {:else}
    <img class="vv-bild" src={vorschauUrl(m)} alt={m.name} loading="lazy" onerror={() => (kaputt = true)} />
  {/if}
  <span class="vv-format">{formatKuerzel(m.name)}</span>
  <!-- Dauerhaft sichtbar: so ist klar, dass es ein Video ist und kein Bild. -->
  {#if abspielen}
    <button
      class="vv-play"
      title="Abspielen"
      aria-label="Abspielen: {m.name}"
      onclick={(e) => {
        e.stopPropagation();
        abspielen();
      }}
      ondblclick={(e) => e.stopPropagation()}
    >
      <i class="fa-solid fa-play"></i>
    </button>
  {:else}
    <span class="vv-play"><i class="fa-solid fa-play"></i></span>
  {/if}
</div>

<style>
  .vv-cover {
    width: 100%; height: 100%; position: relative;
    display: grid; place-items: center; color: #fff;
    border-radius: inherit; overflow: hidden;
    background: #000;
  }
  .vv-cover.ohne-bild {
    background: linear-gradient(135deg, #1f2937, #0f766e);
    font-size: 2.2rem;
  }
  .vv-bild { width: 100%; height: 100%; object-fit: cover; display: block; }
  .vv-film { opacity: 0.9; }
  .vv-format {
    position: absolute; top: 8px; right: 8px; font-size: 0.6rem; font-weight: 600;
    padding: 2px 7px; border-radius: 999px; background: rgba(0, 0, 0, 0.55); color: #fff;
  }
  .vv-play {
    position: absolute;
    color: #fff;
    padding: 0;
    cursor: pointer;
    width: 42px; height: 42px; border-radius: 50%;
    display: grid; place-items: center;
    font-size: 0.95rem;
    background: rgba(0, 0, 0, 0.5);
    border: 2px solid rgba(255, 255, 255, 0.85);
    transition: background 0.15s ease, transform 0.15s ease;
  }
  .vv-play i { margin-left: 2px; } /* optischer Ausgleich des Dreiecks */
  :global(.kachel:hover) .vv-play,
  :global(.vorschau-flaeche:hover) .vv-play {
    background: rgba(0, 0, 0, 0.75);
    transform: scale(1.08);
  }
</style>

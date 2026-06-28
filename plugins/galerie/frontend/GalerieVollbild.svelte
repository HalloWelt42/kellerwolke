<script lang="ts">
  import type { Browser } from "../../lib/browser.svelte";
  import type { Knoten } from "../../lib/types";
  import { inlineUrl } from "./bilder";

  // Vollansicht eines EINZELNEN Bildes als Overlay (aus dem Detail-Pane heraus).
  // Bewusst schlicht: ein Bild + Schliessen. Das Durchblaettern bleibt der
  // Galerie-App vorbehalten.
  interface Props {
    knoten: Knoten;
    browser: Browser;
    schliessen: () => void;
  }
  let { knoten, schliessen }: Props = $props();

  function taste(e: KeyboardEvent) {
    if (e.key === "Escape") schliessen();
  }
</script>

<svelte:window onkeydown={taste} />

<div class="gv-huelle" role="presentation" onclick={schliessen}>
  <img
    class="gv-bild"
    src={inlineUrl(knoten.id)}
    alt={knoten.name}
    role="presentation"
    onclick={(e) => e.stopPropagation()}
  />
  <div class="gv-leiste" role="presentation" onclick={(e) => e.stopPropagation()}>
    <span class="gv-name">{knoten.name}</span>
    <button class="gv-knopf" title="Schließen" aria-label="Schließen" onclick={schliessen}>
      <i class="fa-solid fa-xmark"></i>
    </button>
  </div>
</div>

<style>
  .gv-huelle {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.92);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 70;
  }
  .gv-bild {
    max-width: 96vw;
    max-height: 86vh;
    object-fit: contain;
  }
  .gv-leiste {
    position: absolute;
    bottom: var(--a4);
    left: 50%;
    transform: translateX(-50%);
    display: flex;
    align-items: center;
    gap: var(--a2);
    background: rgba(20, 20, 24, 0.9);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: var(--r3);
    padding: var(--a2) var(--a3);
    color: #fff;
  }
  .gv-name {
    max-width: 40vw;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: 0.86rem;
  }
  .gv-knopf {
    border: none;
    background: transparent;
    color: #fff;
    cursor: pointer;
    font-size: 1rem;
    width: 32px;
    height: 32px;
    border-radius: var(--r1);
  }
  .gv-knopf:hover {
    background: rgba(255, 255, 255, 0.14);
  }
</style>

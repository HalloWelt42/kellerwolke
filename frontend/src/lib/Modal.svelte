<script lang="ts">
  import type { Snippet } from "svelte";

  interface Props {
    titel: string;
    schliessen: () => void;
    children: Snippet;
  }
  let { titel, schliessen, children }: Props = $props();

  function aufHintergrund(e: MouseEvent) {
    if (e.target === e.currentTarget) schliessen();
  }
  function aufTaste(e: KeyboardEvent) {
    if (e.key === "Escape") schliessen();
  }
</script>

<svelte:window onkeydown={aufTaste} />

<div class="hintergrund" onclick={aufHintergrund} role="presentation">
  <div class="modal" role="dialog" aria-modal="true">
    <div class="kopf">
      <h2>{titel}</h2>
      <button class="still" onclick={schliessen} aria-label="Schliessen">
        <i class="fa-solid fa-xmark"></i>
      </button>
    </div>
    <div class="inhalt">
      {@render children()}
    </div>
  </div>
</div>

<style>
  .hintergrund {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.55);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 50;
  }
  .modal {
    background: var(--panel);
    border: 1px solid var(--rand);
    border-radius: var(--radius);
    box-shadow: var(--schatten);
    width: min(440px, 92vw);
    overflow: hidden;
  }
  .kopf {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.9rem 1.1rem;
    border-bottom: 1px solid var(--rand);
  }
  .kopf h2 {
    margin: 0;
    font-size: 1.05rem;
    font-weight: 600;
  }
  .inhalt {
    padding: 1.1rem;
    display: flex;
    flex-direction: column;
    gap: 0.9rem;
  }
</style>

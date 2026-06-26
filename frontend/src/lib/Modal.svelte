<script lang="ts">
  import type { Snippet } from "svelte";

  interface Props {
    titel: string;
    schliessen: () => void;
    children: Snippet;
    breit?: boolean;
  }
  let { titel, schliessen, children, breit = false }: Props = $props();

  function aufHintergrund(e: MouseEvent) {
    if (e.target === e.currentTarget) schliessen();
  }
  function aufTaste(e: KeyboardEvent) {
    if (e.key === "Escape") schliessen();
  }
</script>

<svelte:window onkeydown={aufTaste} />

<div class="modal-hg" onclick={aufHintergrund} role="presentation">
  <div class="modal" class:breit role="dialog" aria-modal="true">
    <div class="modal-kopf">
      <h2>{titel}</h2>
      <button class="icon-knopf" onclick={schliessen} aria-label="Schliessen">
        <i class="fa-solid fa-xmark"></i>
      </button>
    </div>
    <div class="modal-inhalt">
      {@render children()}
    </div>
  </div>
</div>

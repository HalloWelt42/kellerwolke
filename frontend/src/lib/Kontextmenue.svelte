<script lang="ts">
  export interface MenuEintrag {
    label?: string;
    icon?: string;
    gefahr?: boolean;
    trenner?: boolean;
    fn?: () => void;
  }

  interface Props {
    x: number;
    y: number;
    eintraege: MenuEintrag[];
    onClose: () => void;
  }
  let { x, y, eintraege, onClose }: Props = $props();

  // Position so verschieben, dass das Menue im Fenster bleibt.
  function platziere(el: HTMLDivElement) {
    const r = el.getBoundingClientRect();
    const rand = 8;
    let nx = x;
    let ny = y;
    if (nx + r.width > window.innerWidth - rand) nx = window.innerWidth - r.width - rand;
    if (ny + r.height > window.innerHeight - rand) ny = window.innerHeight - r.height - rand;
    el.style.left = `${Math.max(rand, nx)}px`;
    el.style.top = `${Math.max(rand, ny)}px`;
  }

  function waehle(e: MenuEintrag) {
    onClose();
    e.fn?.();
  }
</script>

<svelte:window onkeydown={(e) => e.key === "Escape" && onClose()} onresize={onClose} />

<div
  class="kontext-hg"
  role="presentation"
  onclick={onClose}
  oncontextmenu={(e) => {
    e.preventDefault();
    onClose();
  }}
></div>

<div class="kontextmenue" role="menu" use:platziere>
  {#each eintraege as e, i (i)}
    {#if e.trenner}
      <div class="ktrenner"></div>
    {:else}
      <button class:gefahr={e.gefahr} role="menuitem" onclick={() => waehle(e)}>
        <i class="fa-solid {e.icon}"></i> {e.label}
      </button>
    {/if}
  {/each}
</div>

<style>
  .kontext-hg {
    position: fixed;
    inset: 0;
    z-index: 29;
  }
</style>

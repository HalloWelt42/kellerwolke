<script lang="ts">
  import type { Browser } from "../../lib/browser.svelte";
  import type { Knoten } from "../../lib/types";
  import { thumbUrl } from "./bilder";

  // Eingebettete Vorschau im Detail-Pane: serverseitiges Thumbnail statt Icon.
  interface Props {
    knoten: Knoten;
    browser: Browser;
  }
  let { knoten }: Props = $props();
  let kaputt = $state(false);
</script>

{#if kaputt}
  <i class="fa-regular fa-image"></i>
{:else}
  <img
    class="g-vorschau"
    src={thumbUrl(knoten.id, 480)}
    alt={knoten.name}
    onerror={() => (kaputt = true)}
  />
{/if}

<style>
  .g-vorschau {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
    border-radius: var(--r2);
  }
</style>

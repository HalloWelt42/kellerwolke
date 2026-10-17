<script lang="ts">
  import type { Snippet } from "svelte";

  // Blatt von unten über einem Schleier. Antippen des Schleiers schließt es.
  interface Props {
    schliessen: () => void;
    children: Snippet;
  }
  let { schliessen, children }: Props = $props();
</script>

<div class="m-schleier" role="presentation" onclick={schliessen}></div>
<div class="m-blatt" role="dialog" aria-modal="true">
  <div class="m-griff"></div>
  {@render children()}
</div>

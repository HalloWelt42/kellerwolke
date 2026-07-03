<script lang="ts">
  import type { Browser } from "../../lib/browser.svelte";
  import type { Knoten } from "../../lib/types";
  import { streamUrl, formatKuerzel } from "./medien";
  interface Props { knoten: Knoten; browser: Browser; }
  let { knoten }: Props = $props();
</script>

<div class="av">
  <div class="av-cover"><i class="fa-solid fa-music"></i><span class="av-format">{formatKuerzel(knoten.name)}</span></div>
  <audio class="av-player" controls preload="none" src={streamUrl(knoten.id)}></audio>
</div>

<style>
  .av { width: 100%; height: 100%; display: flex; flex-direction: column; }
  .av-cover { flex: 1; display: grid; place-items: center; color: #fff; font-size: 2rem; position: relative; background: linear-gradient(135deg, #6d5efc, #3b82f6); }
  .av-format { position: absolute; top: 8px; right: 8px; font-size: 0.6rem; font-weight: 600; padding: 2px 7px; border-radius: 999px; background: rgba(0,0,0,0.42); color: #fff; }
  .av-player { width: 100%; }
</style>

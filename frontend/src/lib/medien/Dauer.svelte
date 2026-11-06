<script lang="ts">
  import { dauerAnfordern, dauerText, dauerVon } from "./dauermessung.svelte";

  // Dauer eines Tons oder Videos (mm:ss), gemessen beim ersten Zeigen; bis dahin ein Strich.
  interface Props {
    m: { id: string; etag: string | null };
    art: "audio" | "video";
  }
  let { m, art }: Props = $props();

  $effect(() => {
    dauerAnfordern(m, art);
  });
  const text = $derived(dauerText(dauerVon(m)));
</script>

{text}

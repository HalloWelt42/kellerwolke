<script lang="ts">
  import { dauerAnfordern, dauerText, dauerVon } from "./dauermessung.svelte";

  // Dauer eines Tons oder Videos (mm:ss), gemessen beim ersten Zeigen; bis dahin `leer`. `nachsatz` folgt nur einer
  // bekannten Dauer (etwa " · " vor der Größe in einer Zeile am Telefon).
  interface Props {
    m: { id: string; etag: string | null };
    art: "audio" | "video";
    leer?: string;
    nachsatz?: string;
  }
  let { m, art, leer = "-", nachsatz = "" }: Props = $props();

  $effect(() => {
    dauerAnfordern(m, art);
  });
  const s = $derived(dauerVon(m));
  const bekannt = $derived(s !== undefined && isFinite(s));
</script>

{bekannt ? dauerText(s) + nachsatz : leer}

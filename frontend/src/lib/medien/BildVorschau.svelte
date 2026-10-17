<script lang="ts">
  import { vorschauUrl, type Stufe } from "./adressen";

  // Vorschaubild, das seinen Rahmen füllt. Kommt keins (Fehler, kein Bild), bleibt das Symbol.
  interface Props {
    m: { id: string; etag: string | null; name: string };
    stufe?: Stufe;
  }
  let { m, stufe = "gross" }: Props = $props();
  let kaputt = $state(false);
  // Neuer Eintrag oder neue Version: neuer Versuch.
  $effect(() => {
    void m.id;
    void m.etag;
    kaputt = false;
  });
</script>

{#if kaputt}
  <i class="fa-regular fa-image"></i>
{:else}
  <img class="bv" src={vorschauUrl(m, stufe)} alt={m.name} loading="lazy" onerror={() => (kaputt = true)} />
{/if}

<style>
  .bv { width: 100%; height: 100%; object-fit: cover; display: block; border-radius: var(--r2); }
</style>

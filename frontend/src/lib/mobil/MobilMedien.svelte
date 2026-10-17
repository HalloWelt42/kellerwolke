<script lang="ts">
  import { onMount } from "svelte";
  import { SvelteSet } from "svelte/reactivity";
  import * as api from "../api";
  import type { Medium } from "../types";
  import { beiAenderung } from "../zustand.svelte";
  import { player, aktuelleSpur } from "../player.svelte";
  import { ausMedium, vorschauUrl, type MedienEintrag } from "../medien/adressen";
  import { medienOeffnen } from "../medien/oeffnen";
  import { groesseText } from "../format";
  import { kurzDatum } from "./anzeige";

  // Medien am Telefon: alle eigenen Bilder, Töne oder Videos, nach Monaten. Ein
  // Bild öffnet das Vollbild (wischen für das nächste), ein Ton spielt unten weiter.
  type Art = "bild" | "audio" | "video";
  let art = $state<Art>("bild");
  let alle = $state<Medium[]>([]);
  let geladen = $state(false);
  let fehler = $state("");

  async function laden() {
    try {
      alle = await api.alleMedien();
      fehler = "";
    } catch (f) {
      fehler = (f as Error).message;
    }
    geladen = true;
  }
  onMount(() => {
    laden();
    return beiAenderung(laden);
  });

  // Neueste zuerst, gruppiert nach Monat.
  const eintraege = $derived(
    alle
      .filter((m) => m.art === art)
      .sort((a, b) => b.geaendert_am.localeCompare(a.geaendert_am))
      .map(ausMedium),
  );
  const monate = $derived.by(() => {
    const gruppen: { titel: string; liste: { m: MedienEintrag; i: number }[] }[] = [];
    eintraege.forEach((m, i) => {
      const d = new Date(m.geaendert_am ?? "");
      const titel = isNaN(d.getTime()) ? "Ohne Datum" : d.toLocaleDateString("de-DE", { month: "long", year: "numeric" });
      const letzte = gruppen[gruppen.length - 1];
      if (letzte && letzte.titel === titel) letzte.liste.push({ m, i });
      else gruppen.push({ titel, liste: [{ m, i }] });
    });
    return gruppen;
  });
  const spielId = $derived(aktuelleSpur()?.id ?? null);
  const kaputt = new SvelteSet<string>(); // Vorschau kam nicht: Symbol zeigen
</script>

<div class="m-segment">
  <button class:an={art === "bild"} onclick={() => (art = "bild")}>Bilder</button>
  <button class:an={art === "audio"} onclick={() => (art = "audio")}>Ton</button>
  <button class:an={art === "video"} onclick={() => (art = "video")}>Video</button>
</div>

{#if !geladen}
  <div class="m-leer"><i class="fa-solid fa-circle-notch fa-spin"></i></div>
{:else if fehler && !alle.length}
  <div class="m-leer"><i class="fa-solid fa-triangle-exclamation"></i><p>{fehler}</p></div>
{:else if !eintraege.length}
  <div class="m-leer">
    <i class="fa-regular fa-image"></i>
    <h2>{art === "bild" ? "Noch keine Bilder" : art === "audio" ? "Noch keine Töne" : "Noch keine Videos"}</h2>
    <p>Hochladen geht unter Dateien mit dem Plus.</p>
  </div>
{:else if art === "audio"}
  <div class="m-liste" style="margin-top:6px">
    {#each eintraege as m, i (m.id)}
      <button class="m-zeile" onclick={() => medienOeffnen(eintraege, i)}>
        <i class="fa-solid {spielId === m.id && player.laeuft ? 'fa-circle-pause' : 'fa-circle-play'} m-symbol ton"></i>
        <span class="m-text">
          <span class="m-name" style="display:block">{m.name}</span>
          <span class="m-meta" style="display:block">{[m.groesse != null ? groesseText(m.groesse).replace(".", ",") : "", m.geaendert_am ? kurzDatum(m.geaendert_am) : ""].filter(Boolean).join(" · ")}</span>
        </span>
      </button>
    {/each}
  </div>
{:else}
  {#each monate as g (g.titel)}
    <div class="m-datum">{g.titel}</div>
    <div class="m-raster">
      {#each g.liste as { m, i } (m.id)}
        <button aria-label={m.name} onclick={() => medienOeffnen(eintraege, i)}>
          {#if kaputt.has(m.id)}
            <i class="fa-regular {m.art === 'video' ? 'fa-file-video' : 'fa-image'}" style="font-size:26px"></i>
          {:else}
            <img src={vorschauUrl(m)} alt="" loading="lazy" onerror={() => kaputt.add(m.id)} />
          {/if}
          {#if m.art === "video"}<span class="m-film"><i class="fa-solid fa-play"></i></span>{/if}
        </button>
      {/each}
    </div>
  {/each}
{/if}

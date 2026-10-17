<script lang="ts">
  import { SvelteSet } from "svelte/reactivity";
  import type { Browser } from "../browser.svelte";
  import type { Knoten } from "../types";
  import { vorschauUrl } from "../medien/adressen";
  import { mSymbol, zeilenMeta } from "./anzeige";
  import { offeneAnfrageZu } from "../zustand.svelte";
  import { anfrageStand } from "../anfragestand";
  import { begleiterText, groesseText } from "../format";

  // Ordner und Dateien einer Fläche, wie am Rechner gefiltert und sortiert, am
  // Telefon gruppiert. Antippen öffnet, ⋮ zeigt die Aktionen.
  interface Props {
    browser: Browser;
    oeffnen: (k: Knoten) => void;
    aktionen: (k: Knoten) => void;
    mitOrt?: boolean; // Suche: Ort statt Größe zeigen
  }
  let { browser, oeffnen, aktionen, mitOrt = false }: Props = $props();

  const SCHRITT = 200;
  let sichtbar = $state(SCHRITT);
  $effect(() => {
    void browser.bereich;
    void browser.aktuellerOrdner;
    void browser.geteiltPfad.length;
    sichtbar = SCHRITT;
  });

  // Externe Quellen gibt es nur am Rechner.
  const liste = $derived(browser.sichtbar.filter((k) => k.typ !== "extern"));
  const kaputt = new SvelteSet<string>(); // Vorschau kam nicht: Symbol zeigen
  const ordner = $derived(liste.filter((k) => k.typ !== "datei").slice(0, sichtbar));
  const dateien = $derived(liste.filter((k) => k.typ === "datei").slice(0, Math.max(0, sichtbar - ordner.length)));
  const imPapierkorb = $derived(browser.bereich === "papierkorb");

  function meta(k: Knoten): string {
    if (mitOrt) {
      const ort = k.ort && k.ort.length ? k.ort.join(" / ") : "Meine Dateien";
      return k.im_namen === false ? `${ort} · im Inhalt gefunden` : ort;
    }
    if (browser.bereich === "geteilt" && browser.geteiltPfad.length === 0 && k.besitzer_name) {
      return `von ${k.besitzer_name}`;
    }
    return zeilenMeta(k, imPapierkorb);
  }
</script>

{#snippet zeile(k: Knoten)}
  {@const s = mSymbol(k)}
  {@const anfrage = mitOrt || imPapierkorb ? null : offeneAnfrageZu(k.id)}
  {@const stand = anfrage ? anfrageStand(anfrage) : null}
  <div class="m-zeile-huelle">
    <button class="m-zeile" onclick={() => oeffnen(k)}>
      {#if k.typ === "datei" && (k.medienart === "bild" || k.medienart === "video") && !kaputt.has(k.id)}
        <span class="m-vorschaubild"><img src={vorschauUrl(k, "klein")} alt="" loading="lazy" onerror={() => kaputt.add(k.id)} /></span>
      {:else}
        <i class="fa-solid {s.icon} m-symbol {s.klasse}"></i>
      {/if}
      <span class="m-text">
        <span class="m-name">{k.name}</span>
        <span class="m-meta">
          {#if k.favorit}<i class="fa-solid fa-star"></i>{" "}{/if}
          {#if stand}
            {k.groesse != null ? `${groesseText(k.groesse).replace(".", ",")} · ` : ""}<span class="m-anfrage" class:wartet={stand.wartet}
              ><i class={stand.wartet ? "fa-regular fa-clock" : "fa-solid fa-circle-notch fa-spin"}></i> {stand.text}{stand.zahl ? ` ${stand.zahl}` : ""}</span
            >
          {:else}
            {meta(k)}{#if k.begleiter_anzahl && !imPapierkorb && !mitOrt}{" · "}<span class="m-begleit"
                ><i class="fa-solid fa-paperclip"></i> {begleiterText(k.begleiter_anzahl)}</span
              >{/if}
          {/if}
        </span>
      </span>
    </button>
    {#if k.typ === "ordner" && !imPapierkorb && browser.bereich !== "geteilt" && !mitOrt}
      <button class="m-mehr" aria-label="Aktionen zu {k.name}" onclick={() => aktionen(k)}><i class="fa-solid fa-ellipsis-vertical"></i></button>
    {:else if k.typ === "ordner" || k.typ === "extern"}
      <span class="m-mehr" aria-hidden="true"><i class="fa-solid fa-chevron-right"></i></span>
    {:else}
      <button class="m-mehr" aria-label="Aktionen zu {k.name}" onclick={() => aktionen(k)}><i class="fa-solid fa-ellipsis-vertical"></i></button>
    {/if}
  </div>
{/snippet}

{#if mitOrt}
  <div class="m-gruppe">{liste.length === 1 ? "1 Treffer" : `${liste.length} Treffer`}</div>
  <div class="m-liste">
    {#each liste.slice(0, sichtbar) as k (k.id)}{@render zeile(k)}{/each}
  </div>
{:else}
  {#if ordner.length}
    <div class="m-gruppe">Ordner</div>
    <div class="m-liste">
      {#each ordner as k (k.id)}{@render zeile(k)}{/each}
    </div>
  {/if}
  {#if dateien.length}
    <div class="m-gruppe">Dateien</div>
    <div class="m-liste">
      {#each dateien as k (k.id)}{@render zeile(k)}{/each}
    </div>
  {/if}
{/if}
{#if liste.length > sichtbar}
  <button class="m-weitere" onclick={() => (sichtbar += SCHRITT)}>{liste.length - sichtbar} weitere anzeigen</button>
{/if}

<style>
  .m-zeile-huelle { display: flex; align-items: center; }
  .m-zeile-huelle .m-zeile { flex: 1; min-width: 0; padding-right: 0; }
  .m-zeile-huelle .m-text { display: block; }
  .m-zeile-huelle .m-name, .m-zeile-huelle .m-meta { display: block; }
</style>

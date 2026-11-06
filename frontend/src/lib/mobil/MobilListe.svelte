<script lang="ts">
  import { SvelteSet } from "svelte/reactivity";
  import type { Browser } from "../browser.svelte";
  import type { Knoten } from "../types";
  import { vorschauUrl } from "../medien/adressen";
  import { mSymbol, zeilenMeta } from "./anzeige";
  import { offeneAnfrageZu } from "../zustand.svelte";
  import { anfrageStand } from "../anfragestand";
  import { begleiterText, groesseText } from "../format";
  import { player, aktuelleSpur } from "../player.svelte";
  import Dauer from "../medien/Dauer.svelte";

  // Ordner und Dateien einer Fläche, wie am Rechner gefiltert und sortiert, am
  // Telefon gruppiert. Antippen öffnet, ⋮ zeigt die Aktionen. Je Art eine eigene Ansicht (KW-5): Bilder im Raster
  // zu dritt, Ton als Titelliste mit Nummer und Dauer, Videos mit Standbild und Dauer zu zweit; Ordner stehen immer oben.
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
  // Die Suche bleibt eine Liste mit Ort; sonst zeigt die gewählte Art ihre Ansicht.
  const art = $derived(mitOrt ? "alle" : browser.wirksameArt);
  const spielId = $derived(aktuelleSpur()?.id ?? null);

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

{#snippet zeile(k: Knoten, nummer: number | null = null)}
  {@const s = mSymbol(k)}
  {@const anfrage = mitOrt || imPapierkorb ? null : offeneAnfrageZu(k.id)}
  {@const stand = anfrage ? anfrageStand(anfrage) : null}
  <div class="m-zeile-huelle">
    <button class="m-zeile" class:spielt={spielId === k.id} onclick={() => oeffnen(k)}>
      {#if nummer}
        <span class="m-nummer">{#if spielId === k.id}<i class="fa-solid {player.laeuft ? 'fa-volume-high' : 'fa-pause'}"></i>{:else}{nummer}{/if}</span>
      {:else if k.typ === "datei" && (k.medienart === "bild" || k.medienart === "video") && !kaputt.has(k.id)}
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
            {#if !mitOrt && !imPapierkorb && (k.medienart === "audio" || k.medienart === "video")}<Dauer m={k} art={k.medienart} leer="" nachsatz=" · " />{/if}{meta(k)}{#if k.begleiter_anzahl && !imPapierkorb && !mitOrt}{" · "}<span class="m-begleit"
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
    {#if art === "bild"}
      <div class="m-raster m-fotos">
        {#each dateien as k (k.id)}
          <button aria-label={k.name} onclick={() => oeffnen(k)}>
            {#if kaputt.has(k.id)}
              <i class="fa-regular fa-image" style="font-size:26px"></i>
            {:else}
              <img src={vorschauUrl(k, "klein")} alt="" loading="lazy" onerror={() => kaputt.add(k.id)} />
            {/if}
          </button>
        {/each}
      </div>
    {:else if art === "video"}
      <div class="m-videos">
        {#each dateien as k (k.id)}
          <button class="m-video" aria-label="Abspielen: {k.name}" onclick={() => oeffnen(k)}>
            <span class="m-standbild">
              {#if !kaputt.has(k.id)}<img src={vorschauUrl(k)} alt="" loading="lazy" onerror={() => kaputt.add(k.id)} />{/if}
              <i class="fa-solid fa-play"></i>
              <span class="m-dauer"><Dauer m={k} art="video" leer="" /></span>
            </span>
            <span class="m-name">{k.name}</span>
            <span class="m-meta">{k.groesse != null ? groesseText(k.groesse).replace(".", ",") : ""}</span>
          </button>
        {/each}
      </div>
    {:else}
      <div class="m-gruppe">{art === "audio" ? "Titel" : "Dateien"}</div>
      <div class="m-liste">
        {#each dateien as k, i (k.id)}{@render zeile(k, art === "audio" ? i + 1 : null)}{/each}
      </div>
    {/if}
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

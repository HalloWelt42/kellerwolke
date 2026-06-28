<script lang="ts">
  import { haupt } from "./zustand.svelte";
  import { symbol, groesseText, datum, typLabel } from "./format";
  import type { Knoten } from "./types";
  import { vorschauFuer, vollansichtFuer } from "../plugins/registry.svelte";

  interface Props {
    k: Knoten;
    onTeilen?: (k: Knoten) => void;
  }
  let { k, onTeilen }: Props = $props();

  const sym = $derived(symbol(k));
  // Datei-Faehigkeiten aktiver Plugins (z.B. Bild-Vorschau/Vollbild der Galerie).
  const vorschau = $derived(k.typ === "datei" ? vorschauFuer(k) : null);
  const vollF = $derived(k.typ === "datei" ? vollansichtFuer(k) : null);
  let vollOffen = $state(false);
  // Bei Dateiwechsel die Vollansicht schliessen.
  $effect(() => {
    void k.id;
    vollOffen = false;
  });
  const pfadText = $derived(
    "/" + haupt.pfad.slice(1).map((t) => t.name).join("/") || "/",
  );
  const groesse = $derived(
    k.groesse ?? (haupt.detailVersionen.length ? haupt.detailVersionen[0].groesse : null),
  );
</script>

<aside class="detail">
  <div class="detail-kopf">
    <h2>Details</h2>
    <button class="icon-knopf" aria-label="Schliessen" onclick={() => haupt.schliesseDetail()}>
      <i class="fa-solid fa-xmark"></i>
    </button>
  </div>

  <div class="detail-vorschau" class:ordner={k.typ !== "datei"} class:bild={!!vorschau}>
    {#if vorschau?.vorschau}
      {@const Vorschau = vorschau.vorschau}
      {#if vollF}
        <button class="vorschau-flaeche" title="Vollansicht" onclick={() => (vollOffen = true)}>
          <Vorschau knoten={k} browser={haupt} />
        </button>
      {:else}
        <Vorschau knoten={k} browser={haupt} />
      {/if}
    {:else}
      <i class="fa-solid {sym.icon}"></i>
    {/if}
  </div>

  {#if vollF?.vollansicht}
    {@const Voll = vollF.vollansicht}
    <button class="knopf still detail-vollknopf" onclick={() => (vollOffen = true)}>
      <i class="fa-solid fa-expand"></i> Vollansicht
    </button>
    {#if vollOffen}
      <Voll knoten={k} browser={haupt} schliessen={() => (vollOffen = false)} />
    {/if}
  {/if}

  <div class="detail-name">{k.name}</div>

  <div class="detail-block">
    <h3>Informationen</h3>
    <div class="infozeile"><span>Typ</span><span>{typLabel(k)}</span></div>
    {#if k.typ === "datei"}
      <div class="infozeile">
        <span>Größe</span><span>{groesse != null ? groesseText(groesse) : "-"}</span>
      </div>
    {/if}
    <div class="infozeile"><span>Geändert</span><span>{datum(k.geaendert_am)}</span></div>
    <div class="infozeile"><span>Erstellt</span><span>{datum(k.erstellt_am)}</span></div>
    <div class="infozeile"><span>Pfad</span><span>{pfadText}</span></div>
  </div>

  {#if k.typ === "datei"}
    <div class="detail-block">
      <h3>Versionen</h3>
      {#if haupt.detailVersionen.length === 0}
        <p class="fehler" style="color: var(--text-3);">Keine Versionsdaten.</p>
      {:else}
        <ul class="versionsliste">
          {#each haupt.detailVersionen as v, i (v.id)}
            <li>
              <i class="fa-solid fa-clock-rotate-left"></i>
              <span class="v-datum">{datum(v.erstellt_am)}</span>
              {#if i === 0}<span class="marke-aktuell">aktuell</span>{/if}
              <span class="z-meta">{groesseText(v.groesse)}</span>
            </li>
          {/each}
        </ul>
      {/if}
    </div>

    <div class="detail-block" style="margin-top: auto;">
      <div style="display: flex; gap: var(--a2);">
        <button class="knopf primaer" style="flex: 1;" onclick={() => haupt.herunterladen(k)}>
          <i class="fa-solid fa-download"></i> Herunterladen
        </button>
        {#if haupt.istSchreibbar}
          <button class="knopf" style="flex: 1;" onclick={() => onTeilen?.(k)}>
            <i class="fa-solid fa-share-nodes"></i> Teilen
          </button>
        {/if}
      </div>
    </div>
  {/if}
</aside>

<style>
  /* Vorschau-Box auf Bild umstellen: Plugin-Vorschau fuellt den Rahmen. */
  .detail-vorschau.bild {
    padding: 0;
    overflow: hidden;
    font-size: 0;
  }
  .vorschau-flaeche {
    width: 100%;
    height: 100%;
    padding: 0;
    border: none;
    background: transparent;
    cursor: zoom-in;
    display: block;
  }
  .detail-vollknopf {
    margin: calc(var(--a4) * -1 + var(--a2)) var(--a4) 0;
    align-self: flex-start;
  }
</style>

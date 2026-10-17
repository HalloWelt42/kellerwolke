<script lang="ts">
  import type { Browser } from "./browser.svelte";
  import * as api from "./api";
  import { symbol, groesseText, datum, typLabel, rolleText } from "./format";
  import type { AppAktion, Knoten } from "./types";
  import { aktionAusfuehren } from "./zustand.svelte";
  import BildVorschau from "./medien/BildVorschau.svelte";
  import VideoVorschau from "./medien/VideoVorschau.svelte";
  import AudioVorschau from "./medien/AudioVorschau.svelte";

  // Details der gewählten Datei. Öffnen (Vollansicht oder Wiedergabe) geht über
  // die Ansicht, damit Blättern und Titelliste dieselben Nachbarn haben.
  interface Props {
    browser: Browser;
    k: Knoten;
    onTeilen?: (k: Knoten) => void;
    onOeffnen?: (k: Knoten) => void;
  }
  let { browser, k, onTeilen, onOeffnen }: Props = $props();

  const sym = $derived(symbol(k));
  const art = $derived(k.typ === "datei" ? (k.medienart ?? null) : null);
  const vollansicht = $derived(art === "bild" || art === "video");
  const pfadText = $derived(
    browser.bereich === "geteilt"
      ? ["Geteilt", ...browser.geteiltPfad.map((t) => t.name)].join(" / ")
      : browser.detailPfad === null
        ? "-"
        : ["Meine Dateien", ...browser.detailPfad.map((t) => t.name)].join(" / "),
  );
  const groesse = $derived(
    k.groesse ?? (browser.detailVersionen.length ? browser.detailVersionen[0].groesse : null),
  );

  // Begleitdateien und was die Apps mit der Datei können (nur in den eigenen Dateien).
  const eigen = $derived(browser.bereich !== "papierkorb" && browser.bereich !== "geteilt");
  const begleiter = $derived(eigen ? browser.begleiterVon(k.id) : []);
  const hauptdatei = $derived(k.haupt_id ? (browser.eintraege.find((e) => e.id === k.haupt_id) ?? null) : null);
  let apps = $state<AppAktion[]>([]);
  let lauf = 0;
  $effect(() => {
    const id = k.id;
    const datei = k.typ === "datei" && eigen;
    const meiner = ++lauf;
    apps = [];
    if (!datei) return;
    api.aktionen(id).then(
      (liste) => {
        if (meiner === lauf) apps = liste;
      },
      () => {},
    );
  });

  function appHinweis(a: AppAktion): string {
    if (!a.erreichbar) return `${a.app} gerade aus`;
    if (a.art === "oeffnen") return "";
    return a.erneut ? "neue Version" : a.app;
  }
</script>

<aside class="detail">
  <div class="detail-kopf">
    <h2>Details</h2>
    <button class="icon-knopf" aria-label="Schließen" onclick={() => browser.schliesseDetail()}>
      <i class="fa-solid fa-xmark"></i>
    </button>
  </div>

  <div class="detail-vorschau" class:ordner={k.typ !== "datei"} class:bild={!!art}>
    {#if art === "audio"}
      <AudioVorschau m={k} spielen={() => onOeffnen?.(k)} />
    {:else if vollansicht}
      <button class="vorschau-flaeche" title="Vollansicht" onclick={() => onOeffnen?.(k)}>
        {#if art === "bild"}<BildVorschau m={k} />{:else}<VideoVorschau m={k} />{/if}
      </button>
    {:else}
      <i class="fa-solid {sym.icon}"></i>
    {/if}
  </div>

  {#if vollansicht}
    <button class="knopf still detail-vollknopf" onclick={() => onOeffnen?.(k)}>
      <i class="fa-solid fa-expand"></i> Vollansicht
    </button>
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
    {#if k.rolle}
      <div class="infozeile">
        <span>{rolleText(k.rolle)} zu</span><span>{hauptdatei?.name ?? "einer Datei daneben"}</span>
      </div>
    {/if}
  </div>

  {#if begleiter.length}
    <div class="detail-block">
      <h3>Begleiter</h3>
      <ul class="begleit-liste">
        {#each begleiter as b (b.id)}
          {@const bs = symbol(b)}
          <li>
            <button class="begleit-eintrag" onclick={() => browser.zeigeDetail(b)}>
              <i class="fa-solid {bs.icon}"></i><span class="b-name">{b.name}</span>
              <span class="rolle-chip">{rolleText(b.rolle ?? "")}</span>
              <span class="b-meta">
                {[b.groesse != null ? groesseText(b.groesse) : "", b.begleiter_app ? `von ${b.begleiter_app}` : "", datum(b.geaendert_am)]
                  .filter(Boolean)
                  .join(" · ")}
              </span>
            </button>
          </li>
        {/each}
      </ul>
    </div>
  {/if}

  {#if apps.length}
    <div class="detail-block">
      <h3>Mit Apps</h3>
      <div class="app-knoepfe">
        {#each apps as a (a.zugang_id + a.kennung)}
          <button class="knopf" onclick={() => aktionAusfuehren(a)}>
            <i class="fa-solid {a.symbol}"></i> {a.titel}
            {#if appHinweis(a)}<span class="k-app">{appHinweis(a)}</span>{/if}
          </button>
        {/each}
      </div>
    </div>
  {/if}

  {#if k.typ === "datei"}
    <div class="detail-block">
      <h3>Versionen</h3>
      {#if browser.detailVersionen.length === 0}
        <p class="fehler" style="color: var(--text-3);">Keine Versionsdaten.</p>
      {:else}
        <ul class="versionsliste">
          {#each browser.detailVersionen as v, i (v.id)}
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
        <button class="knopf primaer" style="flex: 1;" onclick={() => browser.herunterladen(k)}>
          <i class="fa-solid fa-download"></i> Herunterladen
        </button>
        {#if browser.rechte.teilen}
          <button class="knopf" style="flex: 1;" onclick={() => onTeilen?.(k)}>
            <i class="fa-solid fa-share-nodes"></i> Teilen
          </button>
        {/if}
      </div>
    </div>
  {/if}
</aside>

<style>
  /* Vorschau-Box auf Bild umstellen: Plugin-Vorschau füllt den Rahmen. */
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

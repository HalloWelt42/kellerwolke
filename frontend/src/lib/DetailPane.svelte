<script lang="ts">
  import type { Browser } from "./browser.svelte";
  import * as api from "./api";
  import { symbol, groesseText, datum, typLabel, rolleText } from "./format";
  import type { AppAktion, Knoten, VerweisEintrag } from "./types";
  import { istDateiartig, istVerweis, liestInhalt, ortText } from "./knoten";
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
  const art = $derived(liestInhalt(k) ? (k.medienart ?? null) : null);
  const verweis = $derived(istVerweis(k));
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

  // Verweise (KW-10): beim Verweis Name und Ort des Originals, bei einer Datei die Verweise darauf.
  let originalOrt = $state<string | null>(null);
  let verweiseDarauf = $state<VerweisEintrag[]>([]);
  let verweisLauf = 0;
  $effect(() => {
    const id = k.id;
    const ziel = verweis && !k.verwaist ? (k.ziel_id ?? null) : null;
    const mitVerweisen = k.typ === "datei" && eigen && !!k.verweis_anzahl;
    const meiner = ++verweisLauf;
    originalOrt = null;
    verweiseDarauf = [];
    if (ziel) {
      api.pfadVon(ziel).then(
        (kette) => {
          if (meiner === verweisLauf) originalOrt = kette.map((t) => t.name).join("/");
        },
        () => {},
      );
    }
    if (mitVerweisen) {
      api.verweiseAuf(id).then(
        (liste) => {
          if (meiner === verweisLauf) verweiseDarauf = liste;
        },
        () => {},
      );
    }
  });

  // Die Prüfsumme kurz (Anfang und Ende), die ganze im Tooltip.
  const pruefsumme = $derived(k.sha256 ?? (browser.detailVersionen.length ? browser.detailVersionen[0].sha256 : null));
  function kurz(sha: string): string {
    return `${sha.slice(0, 12)}...${sha.slice(-4)}`;
  }

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

  <div class="detail-vorschau" class:ordner={!istDateiartig(k)} class:bild={!!art}>
    {#if verweis && k.verwaist}
      <i class="fa-solid fa-link-slash" style="color: var(--warn);"></i>
    {:else if art === "audio"}
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

  {#if verweis}
    <div class="detail-block">
      <h3>Verweis auf</h3>
      {#if k.verwaist}
        <div class="original-karte fehlt">
          <i class="fa-solid fa-link-slash"></i><span class="o-name">Original fehlt</span>
          <span class="o-pfad">
            Das Original wurde endgültig gelöscht oder liegt im Papierkorb. Der Verweis zeigt ins Leere; holt man das Original
            zurück, ist er wieder heil.
          </span>
        </div>
      {:else}
        <div class="original-karte">
          <i class="fa-solid {sym.icon}"></i><span class="o-name">{k.ziel_name ?? "Original"}</span>
          <span class="o-pfad">{originalOrt === null ? "..." : ortText(originalOrt)}</span>
        </div>
        <button class="knopf breit" onclick={() => browser.zumOriginal(k)}>
          <i class="fa-solid fa-arrow-right-to-bracket"></i> Zum Original
        </button>
      {/if}
    </div>
  {/if}

  <div class="detail-block">
    <h3>Informationen</h3>
    {#if verweis}
      <div class="infozeile"><span>Art</span><span>{k.verwaist ? "Verweis, verwaist" : "Verweis, liest das Original"}</span></div>
    {/if}
    {#if !(verweis && k.verwaist)}
      <div class="infozeile"><span>Typ</span><span>{typLabel(k)}</span></div>
    {/if}
    {#if liestInhalt(k)}
      <div class="infozeile">
        <span>Größe</span><span>{groesse != null ? groesseText(groesse) : "-"}{verweis ? " (Original)" : ""}</span>
      </div>
    {/if}
    {#if verweis}
      <div class="infozeile">
        <span>Angelegt</span><span>{datum(k.erstellt_am)}{k.verweis_app ? ` von ${k.verweis_app}` : ""}</span>
      </div>
    {:else}
      <div class="infozeile"><span>Geändert</span><span>{datum(k.geaendert_am)}</span></div>
      <div class="infozeile"><span>Erstellt</span><span>{datum(k.erstellt_am)}</span></div>
    {/if}
    <div class="infozeile"><span>Pfad</span><span>{pfadText}</span></div>
    {#if liestInhalt(k) && pruefsumme}
      <div class="infozeile">
        <span>Prüfsumme</span><span class="pruefsumme" title="sha256 {pruefsumme}">sha256 {kurz(pruefsumme)}</span>
      </div>
    {/if}
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

  {#if verweis && !k.verwaist}
    <div class="detail-block">
      <p class="detail-hinweis">
        Ein Verweis belegt keinen Platz. Löschen nimmt nur den Verweis; das Original bleibt. Ändern lässt sich nur das
        Original.
      </p>
    </div>
  {/if}

  {#if verweiseDarauf.length}
    <div class="detail-block">
      <h3>Verweise darauf</h3>
      <ul class="begleit-liste">
        {#each verweiseDarauf as v (v.id)}
          <li>
            <button class="begleit-eintrag" onclick={() => browser.zeigeEintrag(v.id)}>
              <i class="fa-solid fa-share"></i><span class="b-name">{v.name}</span>
              <span class="verweis-chip">Verweis</span>
              <span class="b-meta">{[ortText(v.ort), v.app ? `von ${v.app}` : ""].filter(Boolean).join(" · ")}</span>
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
  {/if}

  {#if liestInhalt(k)}
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
  {:else if verweis && browser.rechte.loeschen}
    <div class="detail-block" style="margin-top: auto;">
      <button class="knopf" style="width: 100%; justify-content: center;" onclick={() => browser.loeschen([k.id])}>
        <i class="fa-solid fa-trash"></i> Verweis in den Papierkorb
      </button>
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
  .detail-hinweis {
    margin: 0;
    font-size: 0.85rem;
    color: var(--text-3);
  }
  .detail-vollknopf {
    margin: calc(var(--a4) * -1 + var(--a2)) var(--a4) 0;
    align-self: flex-start;
  }
</style>

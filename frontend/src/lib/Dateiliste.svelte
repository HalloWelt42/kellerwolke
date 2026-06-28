<script lang="ts">
  import { onDestroy } from "svelte";
  import { hochladen } from "./zustand.svelte";
  import type { Browser } from "./browser.svelte";
  import { passt, filterAktiv, leererFilter } from "./filter";
  import { groesseText, datum, symbolFuerName, zeitText, symbol } from "./format";
  import type { Knoten } from "./types";
  import Dateizeile from "./Dateizeile.svelte";
  import type { RowAktion } from "./Dateizeile.svelte";
  import Kachel from "./Kachel.svelte";
  import Auswahlleiste from "./Auswahlleiste.svelte";
  import Kontextmenue from "./Kontextmenue.svelte";
  import type { MenuEintrag } from "./Kontextmenue.svelte";
  import Filterleiste from "./Filterleiste.svelte";

  // Eine wiederverwendbare Browsing-Flaeche: rendert genau einen Browser (die
  // Einzelansicht ODER eine Splitscreen-Pane). Alle Interaktionen - Klick,
  // Auswahl, Marquee, Filter, Scroll, Kontextmenue, Drag/Drop - leben hier
  // EINMAL und gelten in jeder Ansicht identisch.
  interface Props {
    browser: Browser;
    aktiv?: boolean; // hat den Tastatur-Fokus (in Split nur die fokussierte Pane)
    mitDetail?: boolean; // Einfachklick auf eine Datei zeigt das Detail-Pane (nur Einzelansicht)
    onTeilen?: (k: Knoten) => void;
    onEndgueltig?: (k: Knoten) => void;
    onAktiv?: () => void;
  }
  let { browser, aktiv = true, mitDetail = true, onTeilen, onEndgueltig, onAktiv }: Props = $props();

  const auswahl = $derived(browser.auswahl);

  // --- Filtern, Sortieren, Lazy-Load -----------------------------------------
  const gefiltert = $derived.by(() => {
    if (!filterAktiv(browser.filter)) return browser.eintraege;
    return browser.eintraege.filter((k) => passt(k.name, browser.filter));
  });

  function typrang(k: Knoten): number {
    return k.typ === "ordner" ? 0 : k.typ === "extern" ? 1 : 2;
  }
  const sortiert = $derived.by(() => {
    const key = browser.sortKey;
    const dir = browser.sortRichtung === "auf" ? 1 : -1;
    return [...gefiltert].sort((a, b) => {
      // Ordner/Externe immer vor Dateien, unabhaengig von der Richtung.
      if (typrang(a) !== typrang(b)) return typrang(a) - typrang(b);
      let v: number;
      if (key === "groesse") v = (a.groesse ?? 0) - (b.groesse ?? 0);
      else if (key === "geaendert")
        v = new Date(a.geaendert_am).getTime() - new Date(b.geaendert_am).getTime();
      else v = a.name.localeCompare(b.name, "de", { sensitivity: "base", numeric: true });
      return v * dir;
    });
  });

  const SCHRITT = 200;
  let sichtbar = $state(SCHRITT);
  const angezeigt = $derived(sortiert.slice(0, sichtbar));
  const mehrVorhanden = $derived(sichtbar < sortiert.length);

  // Schluessel, der sich aendert, wenn Standort, Sortierung oder Filter wechseln
  // (fuer das Zuruecksetzen der Lazy-Grenze; nicht bei Live-Poll).
  const standort = $derived(
    `${browser.bereich}:${browser.aktuellerOrdner ?? ""}:${browser.geteiltPfad.length}`,
  );
  const filterKey = $derived(
    browser.filter.regeln.map((r) => `${r.text}|${r.modus}|${r.caseSensitive}|${r.negiert}`).join("&") +
      ":" +
      browser.filter.verknuepfung,
  );
  let letzterStandort = "";
  $effect(() => {
    // Beim Standortwechsel den Filter dieser Pane leeren (eigener Filter je Pane).
    if (standort !== letzterStandort) {
      letzterStandort = standort;
      browser.filter = leererFilter();
    }
  });
  $effect(() => {
    void standort;
    void filterKey;
    void browser.sortKey;
    void browser.sortRichtung;
    sichtbar = SCHRITT;
  });

  function aufListenScroll() {
    if (!containerEl) return;
    browser.scrollTop = containerEl.scrollTop;
    if (!mehrVorhanden) return;
    if (containerEl.scrollTop + containerEl.clientHeight >= containerEl.scrollHeight - 300) {
      sichtbar += SCHRITT;
    }
  }

  // Auswahl/Marquee arbeiten auf der sortierten Reihenfolge.
  const geordnet = $derived(sortiert.map((k) => k.id));

  // Kopf-Checkbox (Massenauswahl des aktuell Gefilterten/Angezeigten).
  const alleGewaehlt = $derived(geordnet.length > 0 && geordnet.every((id) => auswahl.istGewaehlt(id)));
  const einigeGewaehlt = $derived(geordnet.some((id) => auswahl.istGewaehlt(id)));
  function kopfWaehlen() {
    if (alleGewaehlt) auswahl.leeren();
    else auswahl.alle(geordnet);
  }
  const imPapierkorb = $derived(browser.bereich === "papierkorb");
  const externAnsicht = $derived(browser.bereich === "extern" && browser.externBrowse !== null);
  const modus = $derived<"dateien" | "papierkorb" | "suche">(
    browser.bereich === "papierkorb" ? "papierkorb" : browser.bereich === "suche" ? "suche" : "dateien",
  );

  let umbenennenId = $state<string | null>(null);
  let ziehZielId = $state<string | null>(null);
  let gezogenIds = $state<string[]>([]);
  let verschiebeModus = $state(false);
  let externDrop = $state(false);
  let containerEl = $state<HTMLElement | null>(null);
  let kontext = $state<{ x: number; y: number; eintraege: MenuEintrag[] } | null>(null);

  // --- Auswahl-Klicks ---------------------------------------------------------

  function rowClick(e: MouseEvent, k: Knoten) {
    if (unterdrueckeKlick) {
      unterdrueckeKlick = false;
      return;
    }
    if (verschiebeModus) {
      if (k.typ === "ordner") browser.verschiebe([...auswahl.ids], k.id);
      verschiebeModus = false;
      return;
    }
    // Bearbeitung: Strg/Cmd schaltet um, Shift waehlt den Bereich.
    if (e.metaKey || e.ctrlKey) {
      auswahl.umschalten(k.id);
      return;
    }
    if (e.shiftKey) {
      auswahl.bereich(k.id, geordnet);
      return;
    }
    if (imPapierkorb) {
      auswahl.waehleEinzeln(k.id);
      return;
    }
    // Einfachklick: Ordner/Extern oeffnen; Datei MARKIEREN (nie herunterladen),
    // in der Einzelansicht zusaetzlich das Detail-Pane zeigen.
    if (k.typ === "ordner" || k.typ === "extern") {
      browser.oeffnen(k);
    } else {
      auswahl.waehleEinzeln(k.id);
      if (mitDetail) browser.zeigeDetail(k);
    }
  }

  function boxClick(k: Knoten) {
    auswahl.umschalten(k.id);
  }

  // Doppelklick auf eine Datei laedt sie herunter (das bewusste "ganz holen").
  // Bei Ordnern passiert nichts - der Einfachklick navigiert bereits hinein.
  function rowDblClick(k: Knoten) {
    if (verschiebeModus) return;
    if (k.typ === "datei") browser.herunterladen(k);
  }

  // --- Inline-Umbenennen ------------------------------------------------------

  function umbenennenStart(k: Knoten) {
    auswahl.waehleEinzeln(k.id);
    umbenennenId = k.id;
  }
  function umbenennenFertig(k: Knoten, name: string) {
    if (umbenennenId !== k.id) return;
    umbenennenId = null;
    browser.umbenennen(k, name);
  }
  function umbenennenAbbruch() {
    umbenennenId = null;
  }

  // --- Zeilen-Aktionen --------------------------------------------------------

  function rowAktion(k: Knoten, art: RowAktion) {
    if (art === "herunterladen") browser.herunterladen(k);
    else if (art === "umbenennen") umbenennenStart(k);
    else if (art === "loeschen") browser.loeschen([k.id]);
    else if (art === "wiederherstellen") browser.wiederherstellen([k.id]);
    else if (art === "endgueltig") onEndgueltig?.(k);
    else if (art === "favorit") browser.favoritUmschalten(k);
  }

  // --- Drag-and-drop (verschieben) -------------------------------------------

  function dragStart(e: DragEvent, k: Knoten) {
    const ziel = e.target as HTMLElement;
    if (ziel?.closest?.(".aus-box, button, input, .umbenennen-feld")) {
      e.preventDefault();
      return;
    }
    if (!auswahl.istGewaehlt(k.id)) auswahl.waehleEinzeln(k.id);
    gezogenIds = [...auswahl.ids];
    if (e.dataTransfer) {
      e.dataTransfer.effectAllowed = "move";
      e.dataTransfer.setData("text/kellerwolke", gezogenIds.join(","));
      e.dataTransfer.setDragImage(baueGhost(gezogenIds, k), 16, 16);
    }
  }

  function baueGhost(ids: string[], k: Knoten): HTMLElement {
    const el = document.createElement("div");
    el.className = "drag-ghost";
    el.style.position = "absolute";
    el.style.top = "-1000px";
    el.style.left = "-1000px";
    const text = ids.length === 1 ? k.name : `${ids.length} Objekte verschieben`;
    el.innerHTML = `<span class="zahl-badge">${ids.length}</span><span>${text.replace(/</g, "")}</span>`;
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 0);
    return el;
  }

  function dragEnd() {
    gezogenIds = [];
    ziehZielId = null;
  }

  function ordnerDragOver(e: DragEvent, k: Knoten) {
    if (gezogenIds.length === 0 || gezogenIds.includes(k.id)) return;
    e.preventDefault();
    if (e.dataTransfer) e.dataTransfer.dropEffect = "move";
    ziehZielId = k.id;
  }
  function ordnerDragLeave(k: Knoten) {
    if (ziehZielId === k.id) ziehZielId = null;
  }
  function ordnerDrop(e: DragEvent, k: Knoten) {
    e.preventDefault();
    e.stopPropagation();
    const ids = gezogenIds.filter((id) => id !== k.id);
    ziehZielId = null;
    gezogenIds = [];
    if (ids.length) browser.verschiebe(ids, k.id);
  }

  // --- Externer Datei-Upload per Drop -----------------------------------------

  function hatDateien(e: DragEvent): boolean {
    return Array.from(e.dataTransfer?.types ?? []).includes("Files");
  }
  function flaecheDragOver(e: DragEvent) {
    if (!browser.istSchreibbar || !hatDateien(e)) return;
    e.preventDefault();
    externDrop = true;
  }
  function flaecheDragLeave(e: DragEvent) {
    if (e.target === e.currentTarget) externDrop = false;
  }
  function flaecheDrop(e: DragEvent) {
    if (!browser.istSchreibbar || !hatDateien(e)) return;
    e.preventDefault();
    externDrop = false;
    hochladen(e.dataTransfer?.files ?? null, browser);
  }

  // --- Marquee (Maus-Rechteck) -----------------------------------------------
  // Startet auf leerer Flaeche UND ueber unmarkierten Zeilen (markierte Zeilen
  // sind ziehbar = Verschieben). So laesst sich auch bei voll gefuellter Liste
  // immer ein Auswahl-Rechteck aufziehen.

  let marquee = $state<{ l: number; t: number; w: number; h: number } | null>(null);
  let mqStart: { x: number; y: number } | null = null;
  let mqBasis: string[] = [];
  let mqAktiv = false;
  let mqAufZeile = false;
  let unterdrueckeKlick = false;

  function inhaltspunkt(e: MouseEvent): { x: number; y: number } {
    const rect = containerEl!.getBoundingClientRect();
    return {
      x: e.clientX - rect.left + containerEl!.scrollLeft,
      y: e.clientY - rect.top + containerEl!.scrollTop,
    };
  }

  function flaecheMouseDown(e: MouseEvent) {
    onAktiv?.();
    if (e.button !== 0 || !containerEl) return;
    const ziel = e.target as HTMLElement;
    // Interaktive Bedienelemente nie als Marquee-Start werten.
    if (ziel.closest("button, input, select, a, .aus-box, .umbenennen-feld, .listenkopf, .filterleiste"))
      return;
    const zeileEl = ziel.closest<HTMLElement>(".zeile, .kachel");
    // Eine bereits markierte Zeile ist ziehbar (Verschieben) - kein Marquee.
    if (zeileEl?.dataset.id && auswahl.istGewaehlt(zeileEl.dataset.id)) return;
    mqAufZeile = !!zeileEl;
    mqStart = inhaltspunkt(e);
    mqBasis = e.metaKey || e.ctrlKey || e.shiftKey ? [...auswahl.ids] : [];
    mqAktiv = false;
    window.addEventListener("mousemove", flaecheMouseMove);
    window.addEventListener("mouseup", flaecheMouseUp);
  }

  function flaecheMouseMove(e: MouseEvent) {
    if (!mqStart || !containerEl) return;
    const p = inhaltspunkt(e);
    if (!mqAktiv && Math.abs(p.x - mqStart.x) + Math.abs(p.y - mqStart.y) < 5) return;
    mqAktiv = true;
    unterdrueckeKlick = true;
    const l = Math.min(mqStart.x, p.x);
    const t = Math.min(mqStart.y, p.y);
    const r = Math.max(mqStart.x, p.x);
    const b = Math.max(mqStart.y, p.y);
    marquee = { l, t, w: r - l, h: b - t };

    const treffer: string[] = [];
    containerEl.querySelectorAll<HTMLElement>(".zeile, .kachel").forEach((el) => {
      const id = el.dataset.id;
      if (!id) return;
      const rl = el.offsetLeft;
      const rt = el.offsetTop;
      const rr = rl + el.offsetWidth;
      const rb = rt + el.offsetHeight;
      if (!(rr < l || rl > r || rb < t || rt > b)) treffer.push(id);
    });
    auswahl.ersetze(mqBasis);
    auswahl.vereinige(treffer);
  }

  function flaecheMouseUp() {
    window.removeEventListener("mousemove", flaecheMouseMove);
    window.removeEventListener("mouseup", flaecheMouseUp);
    // Klick (ohne Ziehen) auf LEERE Flaeche hebt die Auswahl auf; ein Klick auf
    // eine Zeile bleibt dem rowClick ueberlassen.
    if (!mqAktiv && mqStart && !mqAufZeile) auswahl.leeren();
    mqStart = null;
    mqAktiv = false;
    marquee = null;
  }

  onDestroy(() => {
    window.removeEventListener("mousemove", flaecheMouseMove);
    window.removeEventListener("mouseup", flaecheMouseUp);
  });

  // --- Kontextmenue -----------------------------------------------------------

  function kontextOeffnen(e: MouseEvent, k: Knoten) {
    e.preventDefault();
    onAktiv?.();
    if (!auswahl.istGewaehlt(k.id)) auswahl.waehleEinzeln(k.id);
    const mehrere = auswahl.anzahl > 1;
    const eintraege: MenuEintrag[] = [];
    if (imPapierkorb) {
      eintraege.push({
        label: "Wiederherstellen",
        icon: "fa-rotate-left",
        fn: () => browser.wiederherstellen([...auswahl.ids]),
      });
      eintraege.push({
        label: "Endgültig löschen",
        icon: "fa-trash",
        gefahr: true,
        fn: () => onEndgueltig?.(k),
      });
    } else {
      if (!mehrere) {
        eintraege.push({ label: "Öffnen", icon: "fa-arrow-up-right-from-square", fn: () => browser.oeffnen(k) });
      }
      if (!mehrere && k.typ === "datei") {
        eintraege.push({ label: "Herunterladen", icon: "fa-download", fn: () => browser.herunterladen(k) });
      } else if (!mehrere && k.typ === "ordner") {
        eintraege.push({
          label: "Als ZIP herunterladen",
          icon: "fa-file-zipper",
          fn: () => browser.zipHerunterladen([k.id], `${k.name}.zip`),
        });
      } else if (mehrere) {
        eintraege.push({ label: "Herunterladen", icon: "fa-download", fn: () => stapelHerunterladen() });
      }
      if (browser.istSchreibbar) {
        if (!mehrere) {
          eintraege.push({ label: "Umbenennen", icon: "fa-pen", fn: () => umbenennenStart(k) });
          eintraege.push({ label: "Teilen", icon: "fa-share-nodes", fn: () => onTeilen?.(k) });
        }
        eintraege.push({
          label: "Verschieben",
          icon: "fa-arrow-right-arrow-left",
          fn: () => (verschiebeModus = true),
        });
        eintraege.push({ trenner: true });
        eintraege.push({
          label: "In den Papierkorb",
          icon: "fa-trash",
          gefahr: true,
          fn: () => browser.loeschen([...auswahl.ids]),
        });
      }
    }
    kontext = { x: e.clientX, y: e.clientY, eintraege };
  }

  // --- Stapel-Aktionen --------------------------------------------------------

  async function stapelHerunterladen() {
    const ids = [...auswahl.ids];
    if (ids.length === 0) return;
    const knoten = ids
      .map((id) => browser.eintraege.find((e) => e.id === id))
      .filter((k): k is Knoten => !!k);
    if (knoten.length === 1 && knoten[0].typ === "datei") {
      await browser.herunterladen(knoten[0]);
      return;
    }
    const name =
      knoten.length === 1 && knoten[0].typ === "ordner" ? `${knoten[0].name}.zip` : "kellerwolke.zip";
    await browser.zipHerunterladen(ids, name);
  }

  // --- Tastatur ---------------------------------------------------------------

  function fenstertaste(e: KeyboardEvent) {
    if (!aktiv) return; // nur die fokussierte Ansicht/Pane reagiert
    const imFeld = (e.target as HTMLElement)?.closest?.("input, textarea, select");
    if (imFeld) return;
    if (e.key === "Escape") {
      if (kontext) kontext = null;
      else if (verschiebeModus) verschiebeModus = false;
      else if (umbenennenId) umbenennenId = null;
      else auswahl.leeren();
    } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "a" && !externAnsicht) {
      e.preventDefault();
      auswahl.alle(geordnet);
    }
  }
</script>

<svelte:window onkeydown={fenstertaste} />

{#if verschiebeModus}
  <div class="verschiebe-hinweis">
    <i class="fa-solid fa-arrow-pointer"></i>
    Zielordner anklicken, um {auswahl.anzahl}
    {auswahl.anzahl === 1 ? "Objekt" : "Objekte"} zu verschieben.
    <button class="knopf still" onclick={() => (verschiebeModus = false)}>Abbrechen</button>
  </div>
{/if}

{#if browser.laden}
  <div class="liste" bind:this={containerEl}>
    <div class="listenkopf">
      <span></span><span>Name</span><span>Größe</span>
      <span class="sp-geaendert">Geändert</span><span></span>
    </div>
    {#each Array(8) as _, i (i)}
      <div class="skelett-zeile">
        <span class="sk kreis"></span>
        <span class="sk" style="width: {40 + ((i * 13) % 45)}%"></span>
        <span class="sk" style="width: 60%"></span>
        <span class="sk" style="width: 80%"></span>
      </div>
    {/each}
  </div>
{:else if externAnsicht}
  <!-- Externe Quelle -->
  <div class="liste" bind:this={containerEl}>
    {#if browser.externEintraege.length === 0}
      <div class="leer">
        <i class="fa-regular fa-folder-open"></i><span>Dieser Ordner ist leer</span>
      </div>
    {:else}
      <div class="listenkopf">
        <span></span><span>Name</span><span>Größe</span>
        <span class="sp-geaendert">Geändert</span><span></span>
      </div>
      {#each browser.externEintraege as e (e.name)}
        <div class="zeile" role="row" tabindex="-1" ondblclick={() => browser.externGehe(e)}>
          <span class="z-aus"></span>
          <span class="z-name">
            <i
              class="sym fa-solid {e.ist_ordner ? 'fa-folder' : symbolFuerName(e.name)}"
              class:ordner={e.ist_ordner}
            ></i>
            <span class="titel">{e.name}</span>
          </span>
          <span class="z-meta">{e.ist_ordner ? "-" : groesseText(e.groesse)}</span>
          <span class="z-meta z-geaendert"></span>
          <span class="z-akt">
            {#if !e.ist_ordner}
              <button class="icon-knopf" title="Herunterladen" onclick={() => browser.externRunter(e)}>
                <i class="fa-solid fa-download"></i>
              </button>
            {/if}
          </span>
        </div>
      {/each}
    {/if}
  </div>
{:else if browser.bereich === "geteilt"}
  <!-- Mit mir geteilt (read-only) -->
  <div class="liste" bind:this={containerEl}>
    {#if browser.eintraege.length === 0}
      <div class="leer">
        <i class="fa-regular fa-share-from-square"></i><span>Nichts mit dir geteilt</span>
      </div>
    {:else}
      <div class="listenkopf">
        <span></span><span>Name</span><span>Größe</span>
        <span class="sp-geaendert">Geändert</span><span></span>
      </div>
      {#each browser.eintraege as k (k.id)}
        {@const sym = symbol(k)}
        <div class="zeile" role="row" tabindex="-1" onclick={() => browser.geteiltOeffnen(k)}>
          <span class="z-aus"></span>
          <span class="z-name">
            <i class="sym fa-solid {sym.icon} {sym.klasse}"></i>
            <span class="titel">{k.name}</span>
            {#if browser.geteiltPfad.length === 0 && k.besitzer_name}
              <span class="von">von {k.besitzer_name}</span>
            {/if}
          </span>
          <span class="z-meta">
            {k.typ === "ordner"
              ? k.kinder_anzahl === 0
                ? "Leer"
                : `${k.kinder_anzahl} Dateien`
              : k.groesse != null
                ? groesseText(k.groesse)
                : "-"}
          </span>
          <span class="z-meta z-geaendert">{datum(k.geaendert_am)}</span>
          <span class="z-akt">
            {#if k.typ === "datei"}
              <button
                class="icon-knopf"
                title="Herunterladen"
                onclick={(e) => {
                  e.stopPropagation();
                  browser.geteiltOeffnen(k);
                }}
              >
                <i class="fa-solid fa-download"></i>
              </button>
            {/if}
          </span>
        </div>
      {/each}
    {/if}
  </div>
{:else}
  <!-- Standard: eigene Dateien / Suche / Favoriten / Papierkorb -->
  <Filterleiste {browser} />
  {#if sortiert.length === 0}
    <div
      class="liste"
      bind:this={containerEl}
      role="presentation"
      onmousedown={flaecheMouseDown}
      ondragover={flaecheDragOver}
      ondragleave={flaecheDragLeave}
      ondrop={flaecheDrop}
    >
      <div class="leer">
        <i class="fa-regular {filterAktiv(browser.filter) ? 'fa-circle-xmark' : 'fa-folder-open'}"></i>
        <span>
          {#if filterAktiv(browser.filter)}Kein Treffer für den Filter
          {:else if browser.bereich === "papierkorb"}Der Papierkorb ist leer
          {:else if browser.bereich === "suche"}Nichts gefunden
          {:else if browser.bereich === "favoriten"}Noch keine Favoriten - markiere Dateien mit dem Stern
          {:else}Dieser Ordner ist leer - Dateien hierher ziehen oder hochladen{/if}
        </span>
      </div>
      {#if externDrop}
        <div class="drop-overlay">
          <i class="fa-solid fa-cloud-arrow-up"></i><span>Dateien hier ablegen zum Hochladen</span>
        </div>
      {/if}
    </div>
  {:else if browser.ansicht === "grid"}
    <div
      class="grid"
      bind:this={containerEl}
      role="presentation"
      onmousedown={flaecheMouseDown}
      onscroll={aufListenScroll}
      ondragover={flaecheDragOver}
      ondragleave={flaecheDragLeave}
      ondrop={flaecheDrop}
    >
      {#each angezeigt as k (k.id)}
        <Kachel
          {k}
          gewaehlt={auswahl.istGewaehlt(k.id)}
          gezogen={gezogenIds.includes(k.id)}
          schreibbar={browser.istSchreibbar}
          umbenennenAktiv={umbenennenId === k.id}
          zielordner={ziehZielId === k.id}
          onClick={(e) => rowClick(e, k)}
          onDblClick={() => rowDblClick(k)}
          onBox={() => boxClick(k)}
          onKontext={(e) => kontextOeffnen(e, k)}
          onDragStart={(e) => dragStart(e, k)}
          onDragEnd={dragEnd}
          onUmbenennenFertig={(name) => umbenennenFertig(k, name)}
          onUmbenennenAbbruch={umbenennenAbbruch}
          onOrdnerDragOver={(e) => ordnerDragOver(e, k)}
          onOrdnerDragLeave={() => ordnerDragLeave(k)}
          onOrdnerDrop={(e) => ordnerDrop(e, k)}
        />
      {/each}
      {#if mehrVorhanden}
        <button class="mehr-laden" style="grid-column: 1 / -1;" onclick={() => (sichtbar += SCHRITT)}>
          <i class="fa-solid fa-chevron-down"></i>
          {sortiert.length - sichtbar} weitere von {sortiert.length} anzeigen
        </button>
      {/if}
      {#if marquee}
        <div
          class="marquee"
          style="left:{marquee.l}px; top:{marquee.t}px; width:{marquee.w}px; height:{marquee.h}px;"
        ></div>
      {/if}
      {#if externDrop}
        <div class="drop-overlay">
          <i class="fa-solid fa-cloud-arrow-up"></i><span>Dateien hier ablegen zum Hochladen</span>
        </div>
      {/if}
    </div>
  {:else}
    <div
      class="liste"
      bind:this={containerEl}
      role="presentation"
      onmousedown={flaecheMouseDown}
      onscroll={aufListenScroll}
      ondragover={flaecheDragOver}
      ondragleave={flaecheDragLeave}
      ondrop={flaecheDrop}
    >
      <div class="listenkopf">
        <span class="z-aus">
          <span
            class="aus-box"
            class:an={alleGewaehlt}
            class:teil={einigeGewaehlt && !alleGewaehlt}
            role="checkbox"
            aria-checked={alleGewaehlt ? "true" : einigeGewaehlt ? "mixed" : "false"}
            tabindex="0"
            title={alleGewaehlt ? "Auswahl aufheben" : "Alle angezeigten wählen"}
            onclick={kopfWaehlen}
            onkeydown={(e) => {
              if (e.key === " " || e.key === "Enter") {
                e.preventDefault();
                kopfWaehlen();
              }
            }}
          >
            <i class="fa-solid {alleGewaehlt ? 'fa-check' : 'fa-minus'}"></i>
          </span>
        </span>
        <button
          class="sortbar"
          class:aktiv={browser.sortKey === "name"}
          title="Nach Name sortieren"
          onclick={() => browser.setzeSortierung("name")}
        >
          Name
          {#if browser.sortKey === "name"}
            <i
              class="fa-solid {browser.sortRichtung === 'auf'
                ? 'fa-arrow-up-short-wide'
                : 'fa-arrow-down-short-wide'}"
            ></i>
          {/if}
        </button>
        <button
          class="sortbar"
          class:aktiv={browser.sortKey === "groesse"}
          title="Nach Größe sortieren"
          onclick={() => browser.setzeSortierung("groesse")}
        >
          Größe
          {#if browser.sortKey === "groesse"}
            <i
              class="fa-solid {browser.sortRichtung === 'auf'
                ? 'fa-arrow-up-short-wide'
                : 'fa-arrow-down-short-wide'}"
            ></i>
          {/if}
        </button>
        <button
          class="sortbar sp-geaendert"
          class:aktiv={browser.sortKey === "geaendert"}
          title="Nach Datum sortieren"
          onclick={() => browser.setzeSortierung("geaendert")}
        >
          {imPapierkorb ? "Gelöscht" : "Geändert"}
          {#if browser.sortKey === "geaendert"}
            <i
              class="fa-solid {browser.sortRichtung === 'auf'
                ? 'fa-arrow-up-short-wide'
                : 'fa-arrow-down-short-wide'}"
            ></i>
          {/if}
        </button>
        <span></span>
      </div>
      {#each angezeigt as k (k.id)}
        <Dateizeile
          {k}
          gewaehlt={auswahl.istGewaehlt(k.id)}
          gezogen={gezogenIds.includes(k.id)}
          schreibbar={browser.istSchreibbar}
          {imPapierkorb}
          umbenennenAktiv={umbenennenId === k.id}
          zielordner={ziehZielId === k.id}
          onClick={(e) => rowClick(e, k)}
          onDblClick={() => rowDblClick(k)}
          onBox={() => boxClick(k)}
          onKontext={(e) => kontextOeffnen(e, k)}
          onDragStart={(e) => dragStart(e, k)}
          onDragEnd={dragEnd}
          onAktion={(art) => rowAktion(k, art)}
          onUmbenennenFertig={(name) => umbenennenFertig(k, name)}
          onUmbenennenAbbruch={umbenennenAbbruch}
          onOrdnerDragOver={(e) => ordnerDragOver(e, k)}
          onOrdnerDragLeave={() => ordnerDragLeave(k)}
          onOrdnerDrop={(e) => ordnerDrop(e, k)}
        />
      {/each}
      {#if mehrVorhanden}
        <button class="mehr-laden" onclick={() => (sichtbar += SCHRITT)}>
          <i class="fa-solid fa-chevron-down"></i>
          {sortiert.length - sichtbar} weitere von {sortiert.length} anzeigen
        </button>
      {/if}
      {#if marquee}
        <div
          class="marquee"
          style="left:{marquee.l}px; top:{marquee.t}px; width:{marquee.w}px; height:{marquee.h}px;"
        ></div>
      {/if}
      {#if externDrop}
        <div class="drop-overlay">
          <i class="fa-solid fa-cloud-arrow-up"></i><span>Dateien hier ablegen zum Hochladen</span>
        </div>
      {/if}
    </div>
  {/if}
{/if}

{#if auswahl.anzahl > 1 && !externAnsicht}
  <Auswahlleiste
    anzahl={auswahl.anzahl}
    {modus}
    onHerunterladen={stapelHerunterladen}
    onVerschieben={() => (verschiebeModus = true)}
    onLoeschen={() => browser.loeschen([...auswahl.ids])}
    onWiederherstellen={() => browser.wiederherstellen([...auswahl.ids])}
    onAbbrechen={() => auswahl.leeren()}
  />
{/if}

{#if kontext}
  <Kontextmenue
    x={kontext.x}
    y={kontext.y}
    eintraege={kontext.eintraege}
    onClose={() => (kontext = null)}
  />
{/if}

<style>
  .verschiebe-hinweis {
    display: flex;
    align-items: center;
    gap: var(--a2);
    margin: 0 var(--a4) var(--a2);
    padding: var(--a2) var(--a3);
    border-radius: var(--r2);
    background: var(--akzent-weich);
    color: var(--akzent-stark);
    font-size: 0.88rem;
  }
  .verschiebe-hinweis .knopf {
    margin-left: auto;
    color: var(--akzent-stark);
  }
  .von {
    color: var(--text-3);
    font-size: 0.78rem;
    white-space: nowrap;
  }
</style>

<script lang="ts">
  import { onDestroy } from "svelte";
  import {
    zustand,
    istSchreibbar,
    oeffnen,
    zeigeDetail,
    herunterladen,
    hochladen,
    umbenennen,
    verschiebe,
    loeschen,
    wiederherstellen,
    externGehe,
    externRunter,
    uploadStoppen,
  } from "./zustand.svelte";
  import { auswahl } from "./auswahl.svelte";
  import { groesseText, datum, symbolFuerName, zeitText } from "./format";
  import type { Knoten } from "./types";
  import Dateizeile from "./Dateizeile.svelte";
  import type { RowAktion } from "./Dateizeile.svelte";
  import Kachel from "./Kachel.svelte";
  import Auswahlleiste from "./Auswahlleiste.svelte";
  import Kontextmenue from "./Kontextmenue.svelte";
  import type { MenuEintrag } from "./Kontextmenue.svelte";

  const geordnet = $derived(zustand.eintraege.map((k) => k.id));
  const imPapierkorb = $derived(zustand.bereich === "papierkorb");
  const externAnsicht = $derived(zustand.bereich === "extern" && zustand.externBrowse !== null);
  const modus = $derived<"dateien" | "papierkorb" | "suche">(
    zustand.bereich === "papierkorb" ? "papierkorb" : zustand.bereich === "suche" ? "suche" : "dateien",
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
    if (verschiebeModus) {
      if (k.typ === "ordner") verschiebe([...auswahl.ids], k.id);
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
    // Ansicht (Einfachklick): Ordner/Extern oeffnen, Datei zeigt das Detail.
    // Kein Download, keine Auswahl - die bleibt der Checkbox vorbehalten.
    if (imPapierkorb) {
      auswahl.waehleEinzeln(k.id);
      return;
    }
    if (k.typ === "ordner" || k.typ === "extern") {
      oeffnen(k);
    } else {
      auswahl.leeren();
      zeigeDetail(k);
    }
  }

  function boxClick(k: Knoten) {
    auswahl.umschalten(k.id);
  }

  // Doppelklick auf eine Datei laedt sie herunter (das bewusste "ganz oeffnen").
  // Bei Ordnern passiert nichts - der Einfachklick navigiert bereits hinein.
  function rowDblClick(k: Knoten) {
    if (verschiebeModus) return;
    if (k.typ === "datei") herunterladen(k);
  }

  // --- Inline-Umbenennen ------------------------------------------------------

  function umbenennenStart(k: Knoten) {
    auswahl.waehleEinzeln(k.id);
    umbenennenId = k.id;
  }
  function umbenennenFertig(k: Knoten, name: string) {
    if (umbenennenId !== k.id) return;
    umbenennenId = null;
    umbenennen(k, name);
  }
  function umbenennenAbbruch() {
    umbenennenId = null;
  }

  // --- Zeilen-Aktionen --------------------------------------------------------

  function rowAktion(k: Knoten, art: RowAktion) {
    if (art === "herunterladen") herunterladen(k);
    else if (art === "umbenennen") umbenennenStart(k);
    else if (art === "loeschen") loeschen([k.id]);
    else if (art === "wiederherstellen") wiederherstellen([k.id]);
  }

  // --- Drag-and-drop (verschieben) -------------------------------------------

  function dragStart(e: DragEvent, k: Knoten) {
    // Nicht ziehen, wenn der Griff die Checkbox, ein Knopf oder das Feld ist.
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
    const text =
      ids.length === 1 ? k.name : `${ids.length} Objekte verschieben`;
    el.innerHTML =
      `<span class="zahl-badge">${ids.length}</span><span>${text.replace(/</g, "")}</span>`;
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
    if (ids.length) verschiebe(ids, k.id);
  }

  // --- Externer Datei-Upload per Drop -----------------------------------------

  function hatDateien(e: DragEvent): boolean {
    return Array.from(e.dataTransfer?.types ?? []).includes("Files");
  }
  function flaecheDragOver(e: DragEvent) {
    if (!istSchreibbar() || !hatDateien(e)) return;
    e.preventDefault();
    externDrop = true;
  }
  function flaecheDragLeave(e: DragEvent) {
    if (e.target === e.currentTarget) externDrop = false;
  }
  function flaecheDrop(e: DragEvent) {
    if (!istSchreibbar() || !hatDateien(e)) return;
    e.preventDefault();
    externDrop = false;
    hochladen(e.dataTransfer?.files ?? null);
  }

  // --- Marquee (Maus-Rechteck) -----------------------------------------------

  let marquee = $state<{ l: number; t: number; w: number; h: number } | null>(null);
  let mqStart: { x: number; y: number } | null = null;
  let mqBasis: string[] = [];
  let mqAktiv = false;

  // Marquee rechnet durchgaengig im Inhaltsraum des Containers (Client-Koordinate
  // minus Container-Rand plus Scroll). So stimmen Anzeige und Treffer auch bei
  // gescrolltem Container ueberein. Treffer werden ueber data-id zugeordnet,
  // nicht ueber den Schleifenindex.
  function inhaltspunkt(e: MouseEvent): { x: number; y: number } {
    const rect = containerEl!.getBoundingClientRect();
    return {
      x: e.clientX - rect.left + containerEl!.scrollLeft,
      y: e.clientY - rect.top + containerEl!.scrollTop,
    };
  }

  function flaecheMouseDown(e: MouseEvent) {
    if (e.button !== 0 || !containerEl) return;
    const ziel = e.target as HTMLElement;
    if (ziel.closest(".zeile, .kachel, .listenkopf, button, input, .auswahlleiste")) return;
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
    if (!mqAktiv && mqStart) {
      // Klick auf leere Flaeche hebt die Auswahl auf.
      auswahl.leeren();
    }
    mqStart = null;
    mqAktiv = false;
    marquee = null;
  }

  // Falls die Komponente waehrend eines laufenden Marquee verschwindet, die
  // fensterweiten Listener sicher abraeumen (kein Leck).
  onDestroy(() => {
    window.removeEventListener("mousemove", flaecheMouseMove);
    window.removeEventListener("mouseup", flaecheMouseUp);
  });

  // --- Kontextmenue -----------------------------------------------------------

  function kontextOeffnen(e: MouseEvent, k: Knoten) {
    e.preventDefault();
    if (!auswahl.istGewaehlt(k.id)) auswahl.waehleEinzeln(k.id);
    const mehrere = auswahl.anzahl > 1;
    const eintraege: MenuEintrag[] = [];
    if (imPapierkorb) {
      eintraege.push({
        label: "Wiederherstellen",
        icon: "fa-rotate-left",
        fn: () => wiederherstellen([...auswahl.ids]),
      });
    } else {
      if (!mehrere) {
        eintraege.push({ label: "Öffnen", icon: "fa-arrow-up-right-from-square", fn: () => oeffnen(k) });
      }
      if (!mehrere && k.typ === "datei") {
        eintraege.push({ label: "Herunterladen", icon: "fa-download", fn: () => herunterladen(k) });
      } else if (mehrere) {
        eintraege.push({
          label: "Herunterladen",
          icon: "fa-download",
          fn: () => stapelHerunterladen(),
        });
      }
      if (istSchreibbar()) {
        if (!mehrere) {
          eintraege.push({ label: "Umbenennen", icon: "fa-pen", fn: () => umbenennenStart(k) });
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
          fn: () => loeschen([...auswahl.ids]),
        });
      }
    }
    kontext = { x: e.clientX, y: e.clientY, eintraege };
  }

  // --- Stapel-Aktionen --------------------------------------------------------

  async function stapelHerunterladen() {
    for (const id of auswahl.ids) {
      const k = zustand.eintraege.find((e) => e.id === id);
      if (k && k.typ === "datei") await herunterladen(k);
    }
  }

  // --- Tastatur ---------------------------------------------------------------

  function fenstertaste(e: KeyboardEvent) {
    const imFeld = (e.target as HTMLElement)?.closest?.("input, textarea");
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

{#if zustand.laden}
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
  <!-- Externe read-only Quelle -->
  <div class="liste" bind:this={containerEl}>
    {#if zustand.externEintraege.length === 0}
      <div class="leer">
        <i class="fa-regular fa-folder-open"></i><span>Dieser Ordner ist leer</span>
      </div>
    {:else}
      <div class="listenkopf">
        <span></span><span>Name</span><span>Größe</span>
        <span class="sp-geaendert">Geändert</span><span></span>
      </div>
      {#each zustand.externEintraege as e (e.name)}
        <div class="zeile" role="row" tabindex="-1" ondblclick={() => externGehe(e)}>
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
              <button class="icon-knopf" title="Herunterladen" onclick={() => externRunter(e)}>
                <i class="fa-solid fa-download"></i>
              </button>
            {/if}
          </span>
        </div>
      {/each}
    {/if}
  </div>
{:else if zustand.eintraege.length === 0}
  <div
    class="liste"
    bind:this={containerEl}
    role="presentation"
    ondragover={flaecheDragOver}
    ondragleave={flaecheDragLeave}
    ondrop={flaecheDrop}
  >
    <div class="leer">
      <i class="fa-regular fa-folder-open"></i>
      <span>
        {#if zustand.bereich === "papierkorb"}Der Papierkorb ist leer
        {:else if zustand.bereich === "suche"}Nichts gefunden
        {:else if zustand.bereich === "extern"}Keine externen Quellen
        {:else}Dieser Ordner ist leer - Dateien hierher ziehen oder hochladen{/if}
      </span>
    </div>
    {#if externDrop}
      <div class="drop-overlay">
        <i class="fa-solid fa-cloud-arrow-up"></i><span>Dateien hier ablegen zum Hochladen</span>
      </div>
    {/if}
  </div>
{:else if zustand.ansicht === "grid"}
  <div
    class="grid"
    bind:this={containerEl}
    role="presentation"
    onmousedown={flaecheMouseDown}
    ondragover={flaecheDragOver}
    ondragleave={flaecheDragLeave}
    ondrop={flaecheDrop}
  >
    {#each zustand.eintraege as k (k.id)}
      <Kachel
        {k}
        gewaehlt={auswahl.istGewaehlt(k.id)}
        gezogen={gezogenIds.includes(k.id)}
        schreibbar={istSchreibbar()}
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
    ondragover={flaecheDragOver}
    ondragleave={flaecheDragLeave}
    ondrop={flaecheDrop}
  >
    <div class="listenkopf">
      <span></span>
      <span class="sortbar">Name <i class="fa-solid fa-arrow-down-short-wide"></i></span>
      <span>Größe</span>
      <span class="sp-geaendert">{imPapierkorb ? "Gelöscht" : "Geändert"}</span>
      <span></span>
    </div>
    {#each zustand.eintraege as k (k.id)}
      <Dateizeile
        {k}
        gewaehlt={auswahl.istGewaehlt(k.id)}
        gezogen={gezogenIds.includes(k.id)}
        schreibbar={istSchreibbar()}
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

{#if zustand.uploads.length > 0}
  <div class="schwebe-karte">
    <div class="schwebe-kopf">
      <h4>
        {zustand.uploads.length}
        {zustand.uploads.length === 1 ? "Datei wird" : "Dateien werden"} hochgeladen
      </h4>
      <button class="icon-knopf" title="Abbrechen" aria-label="Abbrechen" onclick={uploadStoppen}>
        <i class="fa-solid fa-xmark"></i>
      </button>
    </div>
    {#each zustand.uploads as u (u.name)}
      <div class="fz">
        <div class="fz-kopf">
          <span class="fz-name">{u.name}</span><span class="pct">{u.prozent} %</span>
        </div>
        <div class="fortschritt"><span style="width: {u.prozent}%"></span></div>
        <div class="fz-kopf fz-tempo">
          <span>{u.tempo > 0 ? `${groesseText(u.tempo)}/s` : `${groesseText(u.gesamt)}`}</span>
          <span>{u.prozent >= 100 ? "fertig" : zeitText(u.restzeit)}</span>
        </div>
      </div>
    {/each}
  </div>
{/if}

{#if auswahl.anzahl > 1 && !externAnsicht}
  <Auswahlleiste
    anzahl={auswahl.anzahl}
    {modus}
    onHerunterladen={stapelHerunterladen}
    onVerschieben={() => (verschiebeModus = true)}
    onLoeschen={() => loeschen([...auswahl.ids])}
    onWiederherstellen={() => wiederherstellen([...auswahl.ids])}
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
</style>

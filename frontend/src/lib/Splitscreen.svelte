<script lang="ts">
  import { onMount } from "svelte";
  import * as api from "./api";
  import { ladeVorgaenge } from "./zustand.svelte";
  import type { Pfadteil } from "./zustand.svelte";
  import type { Knoten } from "./types";
  import { symbol, groesseText, datum } from "./format";
  import Modal from "./Modal.svelte";

  // Eigenstaendiger Splitscreen-Modus: zwei unabhaengige Datei-Bereiche
  // nebeneinander, jeder mit eigener Navigation und Auswahl. Dateien lassen
  // sich von einem Bereich in den anderen ziehen (verschieben). Der bestehende
  // Einzel-Browser (zustand/Dateiliste) bleibt davon unberuehrt.

  interface Pane {
    pfad: Pfadteil[];
    eintraege: Knoten[];
    laden: boolean;
    auswahl: string[];
  }

  const start = (): Pane => ({
    pfad: [{ id: null, name: "Meine Dateien" }],
    eintraege: [],
    laden: true,
    auswahl: [],
  });

  let panes = $state<Pane[]>([start(), start()]);
  let aktiv = $state(0);
  let ziel = $state<number | null>(null);
  let gezogen = $state<{ pane: number; ids: string[] } | null>(null);

  let ordnerModal = $state<number | null>(null);
  let ordnerName = $state("");

  function ordnerId(p: Pane): string | null {
    return p.pfad[p.pfad.length - 1].id;
  }

  function rang(k: Knoten): number {
    return k.typ === "datei" ? 1 : 0;
  }

  function sortiere(liste: Knoten[]): Knoten[] {
    return [...liste].sort((a, b) =>
      rang(a) !== rang(b)
        ? rang(a) - rang(b)
        : a.name.localeCompare(b.name, "de", { sensitivity: "base", numeric: true }),
    );
  }

  // Pro Pane ein Generationszaehler: bei schneller Navigation darf nur die
  // jeweils neueste Antwort das Ergebnis schreiben (sonst Liste/Pfad-Divergenz).
  const laeufe = [0, 0];
  async function lade(i: number) {
    const meins = ++laeufe[i];
    const p = panes[i];
    p.laden = true;
    let erg: Knoten[];
    try {
      erg = sortiere(await api.kinder(ordnerId(p)));
    } catch {
      erg = [];
    }
    if (meins !== laeufe[i]) return; // veraltete Antwort verwerfen
    p.eintraege = erg;
    p.auswahl = [];
    p.laden = false;
  }

  onMount(() => {
    lade(0);
    lade(1);
  });

  function oeffne(i: number, k: Knoten) {
    aktiv = i;
    if (k.typ === "ordner") {
      panes[i].pfad = [...panes[i].pfad, { id: k.id, name: k.name }];
      lade(i);
    } else if (k.typ === "datei") {
      api.herunterladen(k);
    }
  }

  function gehe(i: number, index: number) {
    aktiv = i;
    panes[i].pfad = panes[i].pfad.slice(0, index + 1);
    lade(i);
  }

  function waehle(i: number, k: Knoten, e: MouseEvent) {
    aktiv = i;
    const p = panes[i];
    if (e.ctrlKey || e.metaKey) {
      p.auswahl = p.auswahl.includes(k.id)
        ? p.auswahl.filter((x) => x !== k.id)
        : [...p.auswahl, k.id];
    } else {
      p.auswahl = [k.id];
    }
  }

  function dragStart(i: number, k: Knoten, e: DragEvent) {
    aktiv = i;
    if (!panes[i].auswahl.includes(k.id)) panes[i].auswahl = [k.id];
    gezogen = { pane: i, ids: [...panes[i].auswahl] };
    if (e.dataTransfer) {
      e.dataTransfer.effectAllowed = "move";
      e.dataTransfer.setData("text/plain", "split");
    }
  }

  function dragEnd() {
    gezogen = null;
    ziel = null;
  }

  function dragOver(i: number, e: DragEvent) {
    if (!gezogen || gezogen.pane === i) return;
    e.preventDefault();
    ziel = i;
  }

  function dragLeave(i: number) {
    if (ziel === i) ziel = null;
  }

  async function drop(i: number, e: DragEvent) {
    e.preventDefault();
    if (!gezogen || gezogen.pane === i) {
      dragEnd();
      return;
    }
    const zielId = ordnerId(panes[i]);
    const ids = gezogen.ids;
    const quelle = gezogen.pane;
    dragEnd();
    for (const id of ids) {
      try {
        await api.verschieben(id, zielId);
      } catch {
        // einzelne Fehler ueberspringen; Ansicht wird danach neu geladen
      }
    }
    await lade(quelle);
    await lade(i);
  }

  function neuerOrdnerStart(i: number) {
    aktiv = i;
    ordnerModal = i;
    ordnerName = "";
  }

  async function neuerOrdnerBestaetigen() {
    const i = ordnerModal;
    if (i === null) return;
    const name = ordnerName.trim();
    if (!name) return;
    try {
      await api.ordnerAnlegen(name, ordnerId(panes[i]));
    } catch {
      // Fehler still; Liste danach neu laden zeigt den Ist-Zustand
    }
    ordnerModal = null;
    ordnerName = "";
    lade(i);
  }

  async function aufUpload(i: number, e: Event) {
    const inp = e.target as HTMLInputElement;
    if (!inp.files) return;
    for (const f of Array.from(inp.files)) {
      try {
        await api.hochladen(f, ordnerId(panes[i]));
      } catch {
        // einzelne Fehler ueberspringen
      }
    }
    inp.value = "";
    lade(i);
    // Jeder Upload startet serverseitig einen Indizierungs-Vorgang - anzeigen.
    ladeVorgaenge();
  }

  function fokus(el: HTMLInputElement) {
    el.focus();
  }
</script>

<div class="split">
  {#each panes as p, i (i)}
    <div
      class="pane"
      class:aktiv={aktiv === i}
      class:ziel={ziel === i}
      role="presentation"
      onmousedown={() => (aktiv = i)}
      ondragover={(e) => dragOver(i, e)}
      ondragleave={() => dragLeave(i)}
      ondrop={(e) => drop(i, e)}
    >
      <div class="pane-kopf">
        <nav class="breadcrumb">
          {#each p.pfad as teil, idx (idx)}
            {#if idx > 0}<i class="fa-solid fa-chevron-right"></i>{/if}
            {#if idx === p.pfad.length - 1}
              <span class="aktuell">{teil.name}</span>
            {:else}
              <a role="button" tabindex="0" onclick={() => gehe(i, idx)}>{teil.name}</a>
            {/if}
          {/each}
        </nav>
        <button
          class="icon-knopf"
          title="Neuer Ordner"
          aria-label="Neuer Ordner"
          onclick={() => neuerOrdnerStart(i)}
        >
          <i class="fa-solid fa-folder-plus"></i>
        </button>
        <label class="icon-knopf" title="Hochladen">
          <i class="fa-solid fa-arrow-up-from-bracket"></i>
          <input type="file" multiple hidden onchange={(e) => aufUpload(i, e)} />
        </label>
      </div>

      <div class="liste">
        {#if p.laden}
          <div class="leer"><i class="fa-solid fa-circle-notch fa-spin"></i></div>
        {:else if p.eintraege.length === 0}
          <div class="leer">
            <i class="fa-regular fa-folder-open"></i><span>Dieser Ordner ist leer</span>
          </div>
        {:else}
          {#each p.eintraege as k (k.id)}
            {@const sym = symbol(k)}
            <div
              class="zeile"
              class:gewaehlt={p.auswahl.includes(k.id)}
              role="row"
              tabindex="-1"
              draggable="true"
              onclick={(e) => waehle(i, k, e)}
              ondblclick={() => oeffne(i, k)}
              ondragstart={(e) => dragStart(i, k, e)}
              ondragend={dragEnd}
            >
              <span class="z-aus">
                <span class="aus-box" class:an={p.auswahl.includes(k.id)}>
                  <i class="fa-solid fa-check"></i>
                </span>
              </span>
              <span class="z-name">
                <i class="sym fa-solid {sym.icon} {sym.klasse}"></i>
                <span class="titel">{k.name}</span>
              </span>
              <span class="z-meta">
                {k.typ === "ordner"
                  ? k.kinder_anzahl
                    ? `${k.kinder_anzahl} Dateien`
                    : "Leer"
                  : k.groesse != null
                    ? groesseText(k.groesse)
                    : "-"}
              </span>
              <span class="z-meta z-geaendert">{datum(k.geaendert_am)}</span>
              <span class="z-akt"></span>
            </div>
          {/each}
        {/if}
      </div>
    </div>
  {/each}
</div>

{#if ordnerModal !== null}
  <Modal titel="Neuer Ordner" schliessen={() => (ordnerModal = null)}>
    <input
      class="feld"
      type="text"
      placeholder="Ordnername"
      bind:value={ordnerName}
      use:fokus
      onkeydown={(e) => e.key === "Enter" && neuerOrdnerBestaetigen()}
    />
    <div class="modal-knoepfe">
      <button class="knopf still" onclick={() => (ordnerModal = null)}>Abbrechen</button>
      <button class="knopf primaer" onclick={neuerOrdnerBestaetigen}>Anlegen</button>
    </div>
  </Modal>
{/if}

<style>
  .modal-knoepfe {
    display: flex;
    justify-content: flex-end;
    gap: var(--a2);
  }
</style>

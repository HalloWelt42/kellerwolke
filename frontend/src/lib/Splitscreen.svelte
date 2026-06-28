<script lang="ts">
  import { onMount } from "svelte";
  import { erzeugeBrowser, type Browser } from "./browser.svelte";
  import { hochladen } from "./zustand.svelte";
  import type { Knoten } from "./types";
  import Breadcrumb from "./Breadcrumb.svelte";
  import Dateiliste from "./Dateiliste.svelte";
  import Modal from "./Modal.svelte";

  // Splitscreen = reine Layout-Huelle: zwei (oder mehr) unabhaengige Browsing-
  // Instanzen nebeneinander, die je dieselbe zentrale Dateiliste rendern. Damit
  // hat jede Pane automatisch Klick, Auswahl, Marquee, Filter, Scroll und
  // Kontextmenue - identisch zur Einzelansicht, ohne Duplikat.
  interface Props {
    onTeilen?: (k: Knoten) => void;
    onEndgueltig?: (k: Knoten) => void;
  }
  let { onTeilen, onEndgueltig }: Props = $props();

  let panes = $state<Browser[]>([erzeugeBrowser(), erzeugeBrowser()]);
  let aktiv = $state(0);
  let ziel = $state<number | null>(null);

  let ordnerModal = $state<number | null>(null);
  let ordnerName = $state("");

  onMount(() => {
    for (const p of panes) p.ladeOrdner();
  });

  // Cross-Pane-Verschieben: zieht man eine Auswahl aus einer Pane auf eine
  // ANDERE, wandert sie in deren aktuellen Ordner. Drops innerhalb derselben
  // Pane (auf Ordner) erledigt die Dateiliste selbst.
  function paneOver(i: number, e: DragEvent) {
    if (aktiv === i) return;
    if (!Array.from(e.dataTransfer?.types ?? []).includes("text/kellerwolke")) return;
    e.preventDefault();
    if (e.dataTransfer) e.dataTransfer.dropEffect = "move";
    ziel = i;
  }
  function paneLeave(i: number) {
    if (ziel === i) ziel = null;
  }
  async function paneDrop(i: number, e: DragEvent) {
    const roh = e.dataTransfer?.getData("text/kellerwolke");
    const ids = (roh ?? "").split(",").filter(Boolean);
    ziel = null;
    if (!ids.length || aktiv === i) return; // nur echte Cross-Pane-Moves
    e.preventDefault();
    const von = aktiv;
    await panes[i].verschiebe(ids, panes[i].aktuellerOrdner);
    await panes[von].ladeOrdner();
  }

  function neuerOrdnerStart(i: number) {
    aktiv = i;
    ordnerModal = i;
    ordnerName = "";
  }
  function neuerOrdnerBestaetigen() {
    const i = ordnerModal;
    if (i === null) return;
    const name = ordnerName.trim();
    if (!name) return;
    panes[i].ordnerAnlegen(name);
    ordnerModal = null;
    ordnerName = "";
  }
  function aufUpload(i: number, e: Event) {
    const inp = e.target as HTMLInputElement;
    hochladen(inp.files, panes[i]);
    inp.value = "";
  }

  function fokus(el: HTMLInputElement) {
    el.focus();
  }
</script>

<div class="split">
  {#each panes as pane, i (pane.id)}
    <div
      class="pane"
      class:aktiv={aktiv === i}
      class:ziel={ziel === i}
      role="presentation"
      ondragover={(e) => paneOver(i, e)}
      ondragleave={() => paneLeave(i)}
      ondrop={(e) => paneDrop(i, e)}
    >
      <div class="pane-kopf">
        <Breadcrumb browser={pane} />
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

      <Dateiliste
        browser={pane}
        mitDetail={false}
        aktiv={aktiv === i}
        onAktiv={() => (aktiv = i)}
        {onTeilen}
        {onEndgueltig}
      />
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

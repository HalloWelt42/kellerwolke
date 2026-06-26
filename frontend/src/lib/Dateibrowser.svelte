<script lang="ts">
  import { onMount } from "svelte";
  import * as api from "./api";
  import type { Knoten } from "./types";
  import Modal from "./Modal.svelte";

  type Ansicht = "ordner" | "papierkorb" | "suche";

  let pfad = $state<{ id: string | null; name: string }[]>([{ id: null, name: "Start" }]);
  let eintraege = $state<Knoten[]>([]);
  let ansicht = $state<Ansicht>("ordner");
  let laden = $state(false);
  let fehler = $state("");
  let suchbegriff = $state("");
  let ziehen = $state(false);
  let dialog = $state<{ art: "ordner" | "umbenennen" | null; knoten?: Knoten; wert: string }>({
    art: null,
    wert: "",
  });

  const aktuellerOrdner = $derived(pfad[pfad.length - 1].id);

  onMount(ladeOrdner);

  async function ladeOrdner() {
    laden = true;
    fehler = "";
    ansicht = "ordner";
    try {
      eintraege = await api.kinder(aktuellerOrdner);
    } catch (f) {
      fehler = (f as Error).message;
    } finally {
      laden = false;
    }
  }

  async function ladePapierkorb() {
    laden = true;
    fehler = "";
    ansicht = "papierkorb";
    try {
      eintraege = await api.papierkorb();
    } catch (f) {
      fehler = (f as Error).message;
    } finally {
      laden = false;
    }
  }

  async function starteSuche(e: Event) {
    e.preventDefault();
    if (!suchbegriff.trim()) {
      await ladeOrdner();
      return;
    }
    laden = true;
    fehler = "";
    ansicht = "suche";
    try {
      eintraege = await api.suchen(suchbegriff.trim());
    } catch (f) {
      fehler = (f as Error).message;
    } finally {
      laden = false;
    }
  }

  function oeffnen(k: Knoten) {
    if (k.typ === "ordner" || k.typ === "extern") {
      pfad = [...pfad, { id: k.id, name: k.name }];
      ladeOrdner();
    } else {
      api.herunterladen(k);
    }
  }

  function breadcrumbGehe(index: number) {
    pfad = pfad.slice(0, index + 1);
    ladeOrdner();
  }

  function neuerOrdner() {
    dialog = { art: "ordner", wert: "" };
  }

  function umbenennenStarten(k: Knoten) {
    dialog = { art: "umbenennen", knoten: k, wert: k.name };
  }

  async function dialogBestaetigen() {
    const wert = dialog.wert.trim();
    if (!wert) return;
    try {
      if (dialog.art === "ordner") {
        await api.ordnerAnlegen(wert, aktuellerOrdner);
      } else if (dialog.art === "umbenennen" && dialog.knoten) {
        await api.umbenennen(dialog.knoten.id, wert);
      }
      dialog = { art: null, wert: "" };
      await ladeOrdner();
    } catch (f) {
      fehler = (f as Error).message;
    }
  }

  async function entfernen(k: Knoten) {
    await api.loeschen(k.id);
    await ladeOrdner();
  }

  async function wiederherstellen(k: Knoten) {
    await api.wiederherstellen(k.id);
    await ladePapierkorb();
  }

  async function dateienHochladen(dateien: FileList | null) {
    if (!dateien || dateien.length === 0) return;
    laden = true;
    try {
      for (const datei of Array.from(dateien)) {
        await api.hochladen(datei, aktuellerOrdner);
      }
      await ladeOrdner();
    } catch (f) {
      fehler = (f as Error).message;
      laden = false;
    }
  }

  function aufDateiwahl(e: Event) {
    const ziel = e.target as HTMLInputElement;
    dateienHochladen(ziel.files);
    ziel.value = "";
  }

  function aufDrop(e: DragEvent) {
    e.preventDefault();
    ziehen = false;
    if (ansicht === "ordner") dateienHochladen(e.dataTransfer?.files ?? null);
  }

  function symbol(k: Knoten): string {
    if (k.typ === "ordner") return "fa-folder";
    if (k.typ === "extern") return "fa-folder-tree";
    return "fa-file";
  }

  function datum(iso: string): string {
    return new Date(iso).toLocaleString("de-DE", { dateStyle: "medium", timeStyle: "short" });
  }
</script>

<div class="werkzeuge">
  <div class="links">
    {#if ansicht === "ordner"}
      <button class="primaer" onclick={neuerOrdner}>
        <i class="fa-solid fa-folder-plus"></i> Neuer Ordner
      </button>
      <label class="hochladen">
        <i class="fa-solid fa-arrow-up-from-bracket"></i> Hochladen
        <input type="file" multiple onchange={aufDateiwahl} hidden />
      </label>
    {/if}
  </div>
  <div class="rechts">
    <form class="suche" onsubmit={starteSuche}>
      <i class="fa-solid fa-magnifying-glass"></i>
      <input type="search" placeholder="Suchen ..." bind:value={suchbegriff} />
    </form>
    <button
      class="still"
      class:aktiv={ansicht === "papierkorb"}
      onclick={ladePapierkorb}
      title="Papierkorb"
    >
      <i class="fa-solid fa-trash"></i>
    </button>
  </div>
</div>

{#if ansicht === "ordner"}
  <nav class="brotkrumen">
    {#each pfad as teil, i}
      {#if i > 0}<i class="fa-solid fa-chevron-right teiler"></i>{/if}
      <button class="krume" onclick={() => breadcrumbGehe(i)}>{teil.name}</button>
    {/each}
  </nav>
{:else}
  <nav class="brotkrumen">
    <button class="krume" onclick={ladeOrdner}><i class="fa-solid fa-arrow-left"></i> Zurück</button>
    <span class="modus">{ansicht === "papierkorb" ? "Papierkorb" : `Suche: ${suchbegriff}`}</span>
  </nav>
{/if}

{#if fehler}<div class="fehler">{fehler}</div>{/if}

<div
  class="bereich"
  class:ziehen
  role="region"
  aria-label="Dateien"
  ondragover={(e) => {
    e.preventDefault();
    if (ansicht === "ordner") ziehen = true;
  }}
  ondragleave={() => (ziehen = false)}
  ondrop={aufDrop}
>
  {#if laden}
    <div class="hinweis"><i class="fa-solid fa-spinner fa-spin"></i> Lädt ...</div>
  {:else if eintraege.length === 0}
    <div class="hinweis leer">
      <i class="fa-regular fa-folder-open"></i>
      <span>{ansicht === "ordner" ? "Dieser Ordner ist leer - Dateien hierher ziehen" : "Nichts gefunden"}</span>
    </div>
  {:else}
    <ul class="liste">
      {#each eintraege as k (k.id)}
        <li>
          <button class="zeile" onclick={() => oeffnen(k)} disabled={ansicht === "papierkorb"}>
            <i class="sym fa-solid {symbol(k)}" class:ordnerfarbe={k.typ !== "datei"}></i>
            <span class="name">{k.name}</span>
            <span class="zeit">{datum(k.geaendert_am)}</span>
          </button>
          <div class="aktionen">
            {#if ansicht === "papierkorb"}
              <button class="still" title="Wiederherstellen" onclick={() => wiederherstellen(k)}>
                <i class="fa-solid fa-rotate-left"></i>
              </button>
            {:else}
              {#if k.typ === "datei"}
                <button class="still" title="Herunterladen" onclick={() => api.herunterladen(k)}>
                  <i class="fa-solid fa-download"></i>
                </button>
              {/if}
              <button class="still" title="Umbenennen" onclick={() => umbenennenStarten(k)}>
                <i class="fa-solid fa-pen"></i>
              </button>
              <button class="still gefahr" title="Löschen" onclick={() => entfernen(k)}>
                <i class="fa-solid fa-trash"></i>
              </button>
            {/if}
          </div>
        </li>
      {/each}
    </ul>
  {/if}
</div>

{#if dialog.art}
  <Modal
    titel={dialog.art === "ordner" ? "Neuer Ordner" : "Umbenennen"}
    schliessen={() => (dialog = { art: null, wert: "" })}
  >
    <input
      type="text"
      bind:value={dialog.wert}
      placeholder="Name"
      onkeydown={(e) => e.key === "Enter" && dialogBestaetigen()}
    />
    <div class="dialog-knoepfe">
      <button class="still" onclick={() => (dialog = { art: null, wert: "" })}>Abbrechen</button>
      <button class="primaer" onclick={dialogBestaetigen}>Speichern</button>
    </div>
  </Modal>
{/if}

<style>
  .werkzeuge {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    padding: 0.9rem 1.1rem 0.4rem;
    flex-wrap: wrap;
  }
  .links,
  .rechts {
    display: flex;
    align-items: center;
    gap: 0.6rem;
  }
  .hochladen {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 14px;
    background: var(--panel-2);
    border: 1px solid var(--rand);
    border-radius: 8px;
    padding: 0.5rem 0.85rem;
    cursor: pointer;
  }
  .hochladen:hover {
    background: var(--rand);
  }
  .suche {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    background: var(--bg);
    border: 1px solid var(--rand);
    border-radius: 8px;
    padding: 0 0.7rem;
  }
  .suche i {
    color: var(--gedaempft);
  }
  .suche input {
    border: none;
    background: transparent;
    width: 14rem;
    padding: 0.5rem 0;
  }
  .aktiv {
    color: var(--akzent);
  }
  .brotkrumen {
    display: flex;
    align-items: center;
    gap: 0.35rem;
    padding: 0.4rem 1.2rem 0.6rem;
    color: var(--gedaempft);
    flex-wrap: wrap;
  }
  .krume {
    background: transparent;
    border: none;
    color: var(--text);
    padding: 0.2rem 0.4rem;
  }
  .krume:hover {
    color: var(--akzent);
    background: transparent;
  }
  .teiler {
    font-size: 0.7rem;
    color: var(--gedaempft);
  }
  .modus {
    color: var(--gedaempft);
    font-size: 0.9rem;
  }
  .fehler {
    margin: 0.4rem 1.2rem;
    color: var(--gefahr);
  }
  .bereich {
    margin: 0.3rem 1.1rem 1.1rem;
    border: 1px dashed transparent;
    border-radius: var(--radius);
    min-height: 60vh;
  }
  .bereich.ziehen {
    border-color: var(--akzent);
    background: var(--akzent-weich);
  }
  .hinweis {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 0.8rem;
    color: var(--gedaempft);
    padding: 5rem 1rem;
  }
  .hinweis.leer i {
    font-size: 2.2rem;
    opacity: 0.6;
  }
  .liste {
    list-style: none;
    margin: 0;
    padding: 0;
  }
  .liste li {
    display: flex;
    align-items: center;
    border-bottom: 1px solid var(--rand);
  }
  .zeile {
    flex: 1;
    display: flex;
    align-items: center;
    gap: 0.9rem;
    background: transparent;
    border: none;
    border-radius: 0;
    padding: 0.7rem 0.9rem;
    text-align: left;
    min-width: 0;
  }
  .zeile:hover:not(:disabled) {
    background: var(--panel-2);
  }
  .zeile:disabled {
    cursor: default;
  }
  .sym {
    color: var(--gedaempft);
    width: 1.2rem;
    text-align: center;
  }
  .sym.ordnerfarbe {
    color: var(--akzent);
  }
  .name {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .zeit {
    color: var(--gedaempft);
    font-size: 0.8rem;
    white-space: nowrap;
  }
  .aktionen {
    display: flex;
    gap: 0.2rem;
    padding-right: 0.6rem;
    opacity: 0;
    transition: opacity 0.1s;
  }
  .liste li:hover .aktionen {
    opacity: 1;
  }
  .dialog-knoepfe {
    display: flex;
    justify-content: flex-end;
    gap: 0.6rem;
  }
</style>

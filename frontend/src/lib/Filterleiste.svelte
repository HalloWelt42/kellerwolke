<script lang="ts">
  import { leereRegel, regelGueltig } from "./filter";
  import type { Browser } from "./browser.svelte";

  // Multipler Filter: mehrere Regeln (Wort/Satz/Regex, Gross-/Kleinschreibung,
  // Negation), verknuepft per UND/ODER. Arbeitet auf dem Filter der uebergebenen
  // Browsing-Instanz. Wir bekommen den ganzen Browser (nicht nur filter), damit
  // die Mutation auf der instanzeigenen, nicht-fremden State laeuft - sonst
  // warnt Svelte 5 ueber Mutation eines Props.
  interface Props {
    browser: Browser;
  }
  let { browser }: Props = $props();
  const filter = $derived(browser.filter);

  function hinzu() {
    browser.filter.regeln = [...browser.filter.regeln, leereRegel()];
  }
  function entferne(i: number) {
    browser.filter.regeln = browser.filter.regeln.filter((_, j) => j !== i);
    if (browser.filter.regeln.length === 0) browser.filter.regeln = [leereRegel()];
  }
  function leeren() {
    browser.filter.regeln = [leereRegel()];
  }
  const mehrere = $derived(filter.regeln.length > 1);
</script>

<div class="filterleiste">
  {#each filter.regeln as r, i (r.id)}
    <div class="filter-regel">
      <i class="fa-solid fa-filter symbol"></i>
      <input
        type="text"
        placeholder="In dieser Ansicht filtern ..."
        bind:value={r.text}
        class:ungueltig={!regelGueltig(r)}
      />
      <select bind:value={r.modus} title="Modus" aria-label="Filtermodus">
        <option value="woerter">Wörter</option>
        <option value="satz">Satz</option>
        <option value="regex">Regex</option>
      </select>
      <button
        type="button"
        class="opt"
        class:an={r.caseSensitive}
        title="Groß-/Kleinschreibung beachten"
        onclick={() => (r.caseSensitive = !r.caseSensitive)}
      >
        Aa
      </button>
      <button
        type="button"
        class="opt"
        class:an={r.negiert}
        title="Ausschließen (enthält NICHT)"
        onclick={() => (r.negiert = !r.negiert)}
      >
        <i class="fa-solid fa-not-equal"></i>
      </button>
      {#if mehrere}
        <button
          type="button"
          class="opt still"
          title="Regel entfernen"
          aria-label="Regel entfernen"
          onclick={() => entferne(i)}
        >
          <i class="fa-solid fa-xmark"></i>
        </button>
      {/if}
    </div>
  {/each}
  <div class="filter-aktionen">
    <button type="button" class="opt still" title="Weitere Filterregel" onclick={hinzu}>
      <i class="fa-solid fa-plus"></i> Regel
    </button>
    {#if mehrere}
      <button
        type="button"
        class="opt verkn"
        title={filter.verknuepfung === "und"
          ? "Alle Regeln müssen passen (UND) - umschalten auf ODER"
          : "Eine Regel genügt (ODER) - umschalten auf UND"}
        onclick={() => (browser.filter.verknuepfung = filter.verknuepfung === "und" ? "oder" : "und")}
      >
        {filter.verknuepfung === "und" ? "UND" : "ODER"}
      </button>
    {/if}
    <button type="button" class="opt still" title="Filter leeren" aria-label="Filter leeren" onclick={leeren}>
      <i class="fa-solid fa-eraser"></i>
    </button>
  </div>
</div>

<style>
  .filterleiste {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--a2);
    padding: var(--a2) var(--a4);
  }
  .filter-regel {
    display: flex;
    align-items: center;
    gap: var(--a1);
    background: var(--flaeche-2);
    border: 1px solid var(--rand);
    border-radius: var(--r2);
    padding: 2px 2px 2px var(--a2);
  }
  .filter-regel .symbol {
    color: var(--text-3);
    font-size: 0.8rem;
  }
  .filter-regel input {
    border: none;
    background: transparent;
    color: var(--text-1);
    font: inherit;
    font-size: 0.86rem;
    padding: var(--a1) var(--a1);
    min-width: 160px;
    outline: none;
  }
  .filter-regel input.ungueltig {
    color: var(--gefahr);
  }
  .filter-regel select {
    border: none;
    background: transparent;
    color: var(--text-2);
    font: inherit;
    font-size: 0.8rem;
    padding: 2px;
    border-radius: var(--r1);
    cursor: pointer;
  }
  .opt {
    border: 1px solid transparent;
    background: transparent;
    color: var(--text-2);
    font: inherit;
    font-size: 0.8rem;
    font-weight: 600;
    min-width: 26px;
    height: 26px;
    padding: 0 var(--a1);
    border-radius: var(--r1);
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 4px;
  }
  .opt:hover {
    background: var(--flaeche-3);
  }
  .opt.an {
    background: var(--akzent-weich);
    color: var(--akzent-stark);
  }
  .opt.still {
    color: var(--text-3);
  }
  .opt.verkn {
    border-color: var(--rand);
    color: var(--akzent-stark);
  }
  .filter-aktionen {
    display: flex;
    align-items: center;
    gap: var(--a1);
  }
</style>

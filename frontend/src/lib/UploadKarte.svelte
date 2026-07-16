<script lang="ts">
  import { zustand, uploadStoppen } from "./zustand.svelte";
  import { groesseText, zeitText } from "./format";

  // Zusammenfassung zuerst: die Karte zeigt EINEN Gesamtbalken und die gerade
  // laufende Datei. Die Einzelliste ist aufklappbar und scrollt INNERHALB der
  // Karte. Dadurch ist die Anzeige konstant gross - egal ob 3 oder 300 Dateien.
  let detailsOffen = $state(false);
  let eingeklappt = $state(false);

  const uploads = $derived(zustand.uploads);
  // Fertige Dateien haben prozent 100; ihr "geladen" wird nicht mehr
  // nachgefuehrt, deshalb fuer die Summe die volle Groesse ansetzen.
  const gesamtBytes = $derived(uploads.reduce((s, u) => s + u.gesamt, 0));
  const geladenBytes = $derived(
    uploads.reduce((s, u) => s + (u.prozent >= 100 ? u.gesamt : u.geladen), 0),
  );
  const fertig = $derived(uploads.filter((u) => u.prozent >= 100).length);
  // Es laeuft immer nur eine Datei zur Zeit (sequenzielle Schleife).
  const aktuell = $derived(uploads.find((u) => u.prozent < 100) ?? null);
  const gesamtProzent = $derived(
    gesamtBytes > 0 ? Math.round((geladenBytes / gesamtBytes) * 100) : 0,
  );
  const tempo = $derived(aktuell?.tempo ?? 0);
  const restzeit = $derived(tempo > 0 ? (gesamtBytes - geladenBytes) / tempo : -1);
</script>

<div class="up-karte" class:eingeklappt>
  <div class="up-kopf">
    <button
      class="icon-knopf"
      title={eingeklappt ? "Ausklappen" : "Einklappen"}
      aria-label={eingeklappt ? "Ausklappen" : "Einklappen"}
      onclick={() => (eingeklappt = !eingeklappt)}
    >
      <i class="fa-solid {eingeklappt ? 'fa-chevron-up' : 'fa-chevron-down'}"></i>
    </button>
    <div class="up-titel">
      <strong>{fertig} von {uploads.length} {uploads.length === 1 ? "Datei" : "Dateien"}</strong>
      {#if !eingeklappt}
        <span class="up-bytes">{groesseText(geladenBytes)} von {groesseText(gesamtBytes)}</span>
      {/if}
    </div>
    <span class="up-pct">{gesamtProzent} %</span>
    <button class="icon-knopf" title="Abbrechen" aria-label="Abbrechen" onclick={uploadStoppen}>
      <i class="fa-solid fa-xmark"></i>
    </button>
  </div>

  <div class="fortschritt"><span style="width: {gesamtProzent}%"></span></div>

  {#if !eingeklappt}
    <div class="up-meta">
      <span>{tempo > 0 ? `${groesseText(tempo)}/s` : "berechne ..."}</span>
      <span>{restzeit >= 0 ? zeitText(restzeit) : ""}</span>
    </div>

    {#if aktuell}
      <div class="up-aktuell" title={aktuell.name}>
        <i class="fa-solid fa-arrow-up-from-bracket"></i>
        <span class="up-name">{aktuell.name}</span>
        <span class="up-apct">{aktuell.prozent} %</span>
      </div>
    {/if}

    {#if uploads.length > 1}
      <button class="up-mehr" onclick={() => (detailsOffen = !detailsOffen)}>
        <i class="fa-solid {detailsOffen ? 'fa-chevron-up' : 'fa-chevron-down'}"></i>
        {detailsOffen ? "Einzelheiten ausblenden" : `Alle ${uploads.length} Dateien zeigen`}
      </button>

      {#if detailsOffen}
        <div class="up-liste">
          {#each uploads as u (u.name)}
            <div class="up-zeile" class:erledigt={u.prozent >= 100}>
              <i
                class="fa-solid {u.prozent >= 100
                  ? 'fa-circle-check'
                  : u === aktuell
                    ? 'fa-arrow-up-from-bracket'
                    : 'fa-clock'}"
              ></i>
              <span class="up-name" title={u.name}>{u.name}</span>
              <span class="up-zpct">
                {#if u.prozent >= 100}fertig
                {:else if u === aktuell}{u.prozent} %
                {:else}{groesseText(u.gesamt)}{/if}
              </span>
            </div>
          {/each}
        </div>
      {/if}
    {/if}
  {/if}
</div>

<style>
  /* Feste Obergrenze: die Karte darf NIE mit der Dateianzahl mitwachsen. */
  .up-karte {
    position: absolute;
    right: var(--a4);
    bottom: var(--a4);
    width: 320px;
    max-height: 60vh;
    display: flex;
    flex-direction: column;
    gap: var(--a2);
    background: var(--flaeche);
    border: 1px solid var(--rand);
    border-radius: var(--r2);
    box-shadow: var(--schatten-2);
    padding: var(--a3);
    z-index: 8;
  }
  .up-kopf {
    display: flex;
    align-items: center;
    gap: var(--a2);
  }
  .up-titel {
    display: flex;
    flex-direction: column;
    min-width: 0;
    flex: 1;
  }
  .up-titel strong {
    font-size: 0.86rem;
    font-weight: 600;
  }
  .up-bytes {
    font-size: 0.72rem;
    color: var(--text-3);
  }
  .up-pct {
    font-size: 0.8rem;
    font-variant-numeric: tabular-nums;
    color: var(--text-2);
  }
  .up-meta {
    display: flex;
    justify-content: space-between;
    font-size: 0.72rem;
    color: var(--text-3);
  }
  .up-aktuell {
    display: flex;
    align-items: center;
    gap: var(--a2);
    font-size: 0.78rem;
    color: var(--text-2);
    min-width: 0;
  }
  .up-aktuell i {
    color: var(--akzent);
    flex: none;
  }
  .up-name {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .up-apct {
    font-variant-numeric: tabular-nums;
    flex: none;
  }
  .up-mehr {
    border: none;
    background: transparent;
    color: var(--text-3);
    font: inherit;
    font-size: 0.74rem;
    padding: 0;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: var(--a1);
    text-align: left;
  }
  .up-mehr:hover {
    color: var(--text-2);
  }
  /* Die Einzelliste scrollt innerhalb der Karte, statt sie aufzublaehen. */
  .up-liste {
    overflow-y: auto;
    min-height: 0;
    max-height: 32vh;
    display: flex;
    flex-direction: column;
    gap: 2px;
    border-top: 1px solid var(--rand);
    padding-top: var(--a2);
  }
  .up-zeile {
    display: flex;
    align-items: center;
    gap: var(--a2);
    font-size: 0.76rem;
    min-width: 0;
  }
  .up-zeile i {
    width: 14px;
    text-align: center;
    flex: none;
    color: var(--text-3);
  }
  .up-zeile.erledigt {
    color: var(--text-3);
  }
  .up-zeile.erledigt i {
    color: var(--gut, var(--akzent));
  }
  .up-zpct {
    font-size: 0.72rem;
    color: var(--text-3);
    flex: none;
    font-variant-numeric: tabular-nums;
  }
</style>

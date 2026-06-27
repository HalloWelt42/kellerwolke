<script lang="ts">
  import {
    zustand,
    vorgaengeUmschalten,
    vorgangAbbrechen,
    vorgaengeAufraeumen,
  } from "./zustand.svelte";
  import type { Vorgang } from "./types";

  const laufend = $derived(zustand.vorgaenge.filter((v) => v.status === "laeuft"));
  const erledigt = $derived(zustand.vorgaenge.filter((v) => v.status !== "laeuft"));

  function symbol(v: Vorgang): string {
    if (v.status === "fertig") return "fa-circle-check";
    if (v.status === "fehler") return "fa-triangle-exclamation";
    if (v.status === "abgebrochen") return "fa-ban";
    if (v.art === "indizierung") return "fa-magnifying-glass-chart";
    return "fa-gear";
  }

  function pillText(status: string): string {
    if (status === "laeuft") return "Läuft";
    if (status === "fertig") return "Fertig";
    if (status === "fehler") return "Fehler";
    return "Abgebrochen";
  }

  function prozent(v: Vorgang): number {
    return v.gesamt > 0 ? Math.round((v.erledigt / v.gesamt) * 100) : 0;
  }
</script>

<aside class="vorgaenge">
  <div class="vorgaenge-kopf">
    <h2><i class="fa-solid fa-list-check"></i> Vorgänge</h2>
    <button class="icon-knopf" title="Schließen" aria-label="Schließen" onclick={vorgaengeUmschalten}>
      <i class="fa-solid fa-xmark"></i>
    </button>
  </div>

  <div class="vorgaenge-liste">
    {#if zustand.vorgaenge.length === 0}
      <div class="leer">
        <i class="fa-solid fa-list-check"></i><span>Keine Vorgänge</span>
      </div>
    {/if}

    {#if laufend.length > 0}
      <div class="vorgaenge-abschnitt">Läuft</div>
      {#each laufend as v (v.id)}
        {@render karte(v)}
      {/each}
    {/if}

    {#if erledigt.length > 0}
      <div class="vorgaenge-abschnitt">Abgeschlossen</div>
      {#each erledigt as v (v.id)}
        {@render karte(v)}
      {/each}
    {/if}
  </div>

  {#if erledigt.length > 0}
    <div class="vorgaenge-fuss">
      <button class="knopf still" onclick={vorgaengeAufraeumen}>
        <i class="fa-solid fa-broom"></i> Aufräumen
      </button>
    </div>
  {/if}
</aside>

{#snippet karte(v: Vorgang)}
  <div class="vorgang">
    <div class="vorgang-kopf">
      <div class="vorgang-titel">
        <i class="fa-solid {symbol(v)}"></i>
        <span>{v.titel}</span>
      </div>
      <span class="status-pill {v.status}">{pillText(v.status)}</span>
    </div>

    {#if v.status === "laeuft" && v.gesamt > 0}
      <div class="fortschritt"><span style="width: {prozent(v)}%"></span></div>
      <div class="vorgang-meta">
        <span>{v.erledigt} von {v.gesamt}</span><span>{prozent(v)} %</span>
      </div>
    {/if}

    {#if v.fehler}
      <div class="vorgang-meta"><span>{v.fehler}</span></div>
    {/if}

    {#if v.status === "laeuft"}
      <div class="vorgang-aktionen">
        <button
          class="icon-knopf gefahr"
          title="Abbrechen"
          aria-label="Abbrechen"
          onclick={() => vorgangAbbrechen(v.id)}
        >
          <i class="fa-solid fa-stop"></i>
        </button>
      </div>
    {/if}
  </div>
{/snippet}

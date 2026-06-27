<script lang="ts">
  import { zustand, schliesseDetail, herunterladen, istSchreibbar } from "./zustand.svelte";
  import { symbol, groesseText, datum, typLabel } from "./format";
  import type { Knoten } from "./types";

  interface Props {
    k: Knoten;
    onTeilen?: (k: Knoten) => void;
  }
  let { k, onTeilen }: Props = $props();

  const sym = $derived(symbol(k));
  const pfadText = $derived(
    "/" + zustand.pfad.slice(1).map((t) => t.name).join("/") || "/",
  );
  const groesse = $derived(
    k.groesse ?? (zustand.detailVersionen.length ? zustand.detailVersionen[0].groesse : null),
  );
</script>

<aside class="detail">
  <div class="detail-kopf">
    <h2>Details</h2>
    <button class="icon-knopf" aria-label="Schliessen" onclick={schliesseDetail}>
      <i class="fa-solid fa-xmark"></i>
    </button>
  </div>

  <div class="detail-vorschau" class:ordner={k.typ !== "datei"}>
    <i class="fa-solid {sym.icon}"></i>
  </div>

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
  </div>

  {#if k.typ === "datei"}
    <div class="detail-block">
      <h3>Versionen</h3>
      {#if zustand.detailVersionen.length === 0}
        <p class="fehler" style="color: var(--text-3);">Keine Versionsdaten.</p>
      {:else}
        <ul class="versionsliste">
          {#each zustand.detailVersionen as v, i (v.id)}
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
        <button class="knopf primaer" style="flex: 1;" onclick={() => herunterladen(k)}>
          <i class="fa-solid fa-download"></i> Herunterladen
        </button>
        {#if istSchreibbar()}
          <button class="knopf" style="flex: 1;" onclick={() => onTeilen?.(k)}>
            <i class="fa-solid fa-share-nodes"></i> Teilen
          </button>
        {/if}
      </div>
    </div>
  {/if}
</aside>

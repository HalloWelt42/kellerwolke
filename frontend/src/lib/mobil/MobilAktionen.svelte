<script lang="ts">
  import * as api from "../api";
  import { haupt } from "../zustand.svelte";
  import type { Knoten } from "../types";
  import { mSymbol, zeilenMeta } from "./anzeige";
  import { kannTeilen, teilenOderSichern } from "./teilen";
  import { blattOeffnen, blattSchliessen, mobil, zeigeReiter } from "./mobil.svelte";

  // Aktionen zu einem Eintrag, nur was der Bereich erlaubt (dieselben Rechte wie am Rechner).
  interface Props {
    knoten: Knoten;
    oeffnen: (k: Knoten) => void;
  }
  let { knoten: k, oeffnen }: Props = $props();

  const rechte = $derived(haupt.rechte);
  const s = $derived(mSymbol(k));
  const imPapierkorb = $derived(haupt.bereich === "papierkorb");
  const eigen = $derived(haupt.bereich !== "geteilt");

  // Erst ausführen, dann schließen: nach dem Schließen gibt es dieses Bauteil (und seine Werte) nicht mehr.
  function und(fn: () => void) {
    return () => {
      fn();
      blattSchliessen();
    };
  }

  async function zumOrdner() {
    const ziel = { id: k.id, name: k.name, typ: k.typ };
    blattSchliessen();
    let kette: { id: string | null; name: string }[] = [];
    try {
      kette = await api.pfadVon(ziel.id);
    } catch {
      // ohne Kette in die Wurzel
    }
    mobil.dateienPfad = ziel.typ === "ordner" ? [...kette, { id: ziel.id, name: ziel.name }] : kette;
    zeigeReiter("dateien");
  }
</script>

<div class="m-blatt-kopf">
  <i class="fa-solid {s.icon} m-symbol {s.klasse}"></i>
  <div class="m-text"><div class="m-name">{k.name}</div><div class="m-meta">{zeilenMeta(k, imPapierkorb)}</div></div>
</div>

{#if imPapierkorb}
  <button class="m-aktion" onclick={und(() => haupt.wiederherstellen([k.id]))}><i class="fa-solid fa-rotate-left"></i> Wiederherstellen</button>
  <button class="m-aktion gefahr" onclick={() => blattOeffnen({ art: "halten", knoten: k, was: "endgueltig" })}>
    <i class="fa-solid fa-trash"></i> Endgültig löschen<span class="m-hinweis">halten</span>
  </button>
{:else}
  <button class="m-aktion" onclick={und(() => oeffnen(k))}><i class="fa-solid fa-eye"></i> Öffnen</button>
  {#if k.typ === "datei"}
    <button class="m-aktion" onclick={und(() => teilenOderSichern(k))}>
      {#if kannTeilen()}<i class="fa-solid fa-arrow-up-from-bracket"></i> Teilen oder sichern<span class="m-hinweis">Telefon</span>
      {:else}<i class="fa-solid fa-download"></i> Herunterladen{/if}
    </button>
  {/if}
  {#if rechte.favorit}
    <button class="m-aktion" class:an={k.favorit} onclick={und(() => haupt.favoritUmschalten(k))}>
      <i class="fa-{k.favorit ? 'solid' : 'regular'} fa-star"></i> {k.favorit ? "Aus Favoriten nehmen" : "Zu Favoriten"}
    </button>
  {/if}
  {#if eigen && haupt.bereich !== "dateien"}
    <button class="m-aktion" onclick={zumOrdner}><i class="fa-solid fa-folder-open"></i> Im Ordner zeigen</button>
  {/if}
  {#if rechte.umbenennen}
    <button class="m-aktion" onclick={() => blattOeffnen({ art: "umbenennen", knoten: k })}><i class="fa-solid fa-pen"></i> Umbenennen</button>
  {/if}
  {#if rechte.verschieben}
    <button class="m-aktion" onclick={und(() => haupt.verschiebenBeginnen([k.id]))}><i class="fa-solid fa-arrow-right-arrow-left"></i> Verschieben</button>
  {/if}
  {#if rechte.loeschen}
    <button class="m-aktion gefahr" onclick={() => blattOeffnen({ art: "halten", knoten: k, was: "loeschen" })}>
      <i class="fa-solid fa-trash"></i> In den Papierkorb<span class="m-hinweis">halten</span>
    </button>
  {/if}
{/if}

<script lang="ts">
  import * as api from "../api";
  import { haupt, endgueltigLoeschen } from "../zustand.svelte";
  import { begleiterText, rollenSymbol, symbolFuerName } from "../format";
  import { ortText, verweiseText } from "../knoten";
  import type { Folge } from "../types";
  import { mSymbol } from "./anzeige";
  import HaltenKnopf from "./HaltenKnopf.svelte";
  import { blattSchliessen, type EintragKurz } from "./mobil.svelte";

  // Bestätigung per Halten: in den Papierkorb (wiederherstellbar) oder endgültig. Nimmt das Löschen Begleiter oder
  // Verweise von anderswo mit, stehen sie vorher mit Pfaden da (KW-10); erst dann lässt sich halten.
  interface Props {
    knoten: EintragKurz;
    was: "loeschen" | "endgueltig";
    fertig?: () => void;
  }
  let { knoten: k, was, fertig }: Props = $props();
  const s = $derived(mSymbol(k));

  let folgen = $state<Folge[] | null>(null);
  let fehler = $state("");
  $effect(() => {
    const id = k.id;
    folgen = was === "loeschen" ? null : [];
    fehler = "";
    if (was !== "loeschen") return;
    api.loeschfolgen([id]).then(
      (liste) => {
        if (k.id === id) folgen = liste;
      },
      (f) => (fehler = (f as Error).message),
    );
  });
  const verweise = $derived((folgen ?? []).filter((f) => f.art === "verweis"));
  const begleiter = $derived((folgen ?? []).filter((f) => f.art === "begleiter"));
  const haltenText = $derived(
    was === "endgueltig"
      ? "Halten zum endgültigen Löschen"
      : folgen && folgen.length
        ? `Halten: alle ${folgen.length + 1} in den Papierkorb`
        : "Halten zum Löschen",
  );

  // Erst alles festhalten, dann das Blatt schließen: danach gibt es dieses Bauteil nicht mehr.
  async function ausloesen() {
    const id = k.id;
    const art = was;
    const danach = fertig;
    blattSchliessen();
    if (art === "loeschen") await haupt.loeschenBestaetigt([id]);
    else await endgueltigLoeschen(haupt, [id]);
    danach?.();
  }
</script>

<div class="m-blatt-kopf">
  <i class="fa-solid {s.icon} m-symbol {s.klasse}"></i>
  <div class="m-text">
    <div class="m-name">{k.name}</div>
    <div class="m-meta">
      {was === "loeschen" ? "Kommt in den Papierkorb und lässt sich dort wiederherstellen" : "Wird endgültig gelöscht und lässt sich nicht zurückholen"}
    </div>
  </div>
</div>
{#if folgen && folgen.length}
  <p class="m-folgen-text">{k.typ === "ordner" ? "Mit dem Ordner" : "Mit dem Original"} kommen in den Papierkorb:</p>
  <ul class="m-folgen">
    {#if verweise.length}
      <li class="f-kopf">{verweiseText(verweise.length)}</li>
      {#each verweise as f (f.id)}
        <li><i class="fa-solid fa-share"></i><span class="f-name">{f.name}</span><span class="f-pfad">{ortText(f.ort)}</span></li>
      {/each}
    {/if}
    {#if begleiter.length}
      <li class="f-kopf">{begleiterText(begleiter.length)}</li>
      {#each begleiter as f (f.id)}
        <li>
          <i class="fa-solid {rollenSymbol(f.rolle) ?? symbolFuerName(f.name)}"></i><span class="f-name">{f.name}</span>
          <span class="f-pfad">{ortText(f.ort)}</span>
        </li>
      {/each}
    {/if}
  </ul>
  <p class="m-folgen-text" style="color: var(--m-text-3); font-size: var(--m-marke);">Wiederherstellen holt alle zusammen zurück.</p>
{/if}
{#if fehler}
  <span class="m-leise">{fehler}</span>
{:else if folgen === null}
  <span class="m-leise"><i class="fa-solid fa-circle-notch fa-spin"></i> Folgen werden geprüft</span>
{:else}
  <HaltenKnopf text={haltenText} {ausloesen} />
  <span class="m-leise">Loslassen bricht ab</span>
{/if}

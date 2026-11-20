<script lang="ts">
  import type { Browser } from "./browser.svelte";
  import Modal from "./Modal.svelte";
  import { begleiterText, rolleText, rollenSymbol, symbolFuerName } from "./format";
  import { ortText, verweiseText } from "./knoten";

  // Folgenvorschau vor dem Löschen (KW-10): was mit der Auswahl in den Papierkorb käme (Verweise von anderswo,
  // Begleiter), je mit Pfad. Erst die ausdrückliche Bestätigung löscht; Wiederherstellen holt alles gemeinsam zurück.
  interface Props {
    browser: Browser;
  }
  let { browser }: Props = $props();

  const frage = $derived(browser.loeschFrage);
  const verweise = $derived(frage ? frage.folgen.filter((f) => f.art === "verweis") : []);
  const begleiter = $derived(frage ? frage.folgen.filter((f) => f.art === "begleiter") : []);
  const titel = $derived.by(() => {
    if (!frage) return "";
    return frage.knoten.length === 1 ? `"${frage.knoten[0].name}" in den Papierkorb` : `${frage.knoten.length} Objekte in den Papierkorb`;
  });
  // Wer etwas mitnimmt: ein Original, ein Ordner oder eine Auswahl (dann steht an jedem Verweis, worauf er zeigt).
  const wer = $derived<"original" | "ordner" | "auswahl">(
    !frage || frage.knoten.length !== 1 ? "auswahl" : frage.knoten[0].typ === "ordner" ? "ordner" : "original",
  );
  const womit = $derived({ original: "Mit dem Original", ordner: "Mit dem Ordner", auswahl: "Mit der Auswahl" }[wer]);
  const zurueck = $derived(
    { original: "das Original mit seinen", ordner: "den Ordner mit den", auswahl: "die Auswahl mit den" }[wer] +
      " " +
      [verweise.length ? "Verweisen" : "", begleiter.length ? "Begleitern" : ""].filter(Boolean).join(" und "),
  );
  const gesamt = $derived(frage ? frage.knoten.length + frage.folgen.length : 0);

  function bestaetigen() {
    if (frage) browser.loeschenBestaetigt(frage.knoten.map((k) => k.id));
  }
</script>

{#if frage}
  <Modal {titel} breit schliessen={() => browser.loeschFrageAbbrechen()}>
    <p class="folgen-text">{womit} kommen in den Papierkorb:</p>
    <ul class="folgen-liste">
      {#if verweise.length}
        <li class="f-kopf">{verweiseText(verweise.length)}</li>
        {#each verweise as f (f.id)}
          <li>
            <i class="fa-solid fa-share"></i><span class="f-name">{f.name}</span><span class="verweis-chip">Verweis</span>
            <span class="f-pfad">{ortText(f.ort)}{wer === "original" ? "" : ` · auf ${f.zu_name}`}</span>
          </li>
        {/each}
      {/if}
      {#if begleiter.length}
        <li class="f-kopf">{begleiterText(begleiter.length)}</li>
        {#each begleiter as f (f.id)}
          <li>
            <i class="fa-solid {rollenSymbol(f.rolle) ?? symbolFuerName(f.name)}"></i><span class="f-name">{f.name}</span>
            <span class="rolle-chip">{rolleText(f.rolle ?? "")}</span>
            <span class="f-pfad">{ortText(f.ort)}</span>
          </li>
        {/each}
      {/if}
    </ul>
    <p class="folgen-hinweis">Alles bleibt zusammen: Wiederherstellen holt {zurueck} zurück an ihre Orte.</p>
    <div class="modal-knoepfe">
      <button class="knopf still" onclick={() => browser.loeschFrageAbbrechen()}>Abbrechen</button>
      <button class="knopf primaer" onclick={bestaetigen}>
        <i class="fa-solid fa-trash"></i> Alle {gesamt} in den Papierkorb
      </button>
    </div>
  </Modal>
{/if}

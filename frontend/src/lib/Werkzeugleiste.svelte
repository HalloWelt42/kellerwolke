<script lang="ts">
  import { zustand, haupt, hochladen, navUmschalten } from "./zustand.svelte";
  import { ARTEN_BEREICHE, KACHELGROESSEN, type Kachelgroesse } from "./ansicht.svelte";
  import { alleAbspielen, diashowDerFlaeche } from "./medien/oeffnen";
  import ArtWahl from "./ArtWahl.svelte";

  interface Props {
    onNeuerOrdner: () => void;
    onPapierkorbLeeren: () => void;
  }
  let { onNeuerOrdner, onPapierkorbLeeren }: Props = $props();

  // Globale Werkzeugleiste für die Einzelansicht (haupt), nach dem Entwurf mockups/medien-in-dateien.html (KW-5):
  // Anlegen und Hochladen, Filter nach Art mit der Aktion der Art (Diashow, alles abspielen), rechts die Darstellung
  // (Liste, Kacheln in drei Größen, geteilte Ansicht). Symbole, der Text steht im Hover. Der Namensfilter sitzt je
  // Fläche in der Dateiliste; im Splitscreen liegen Anlegen und Hochladen je Pane.
  const istSplit = $derived(zustand.split && haupt.bereich === "dateien");
  const mitArten = $derived(ARTEN_BEREICHE.includes(haupt.bereich) && !istSplit);
  const art = $derived(haupt.wirksameArt);
  const diashowMoeglich = $derived(mitArten && haupt.artZahlen.bild > 0 && (art === "alle" || art === "bild"));
  const abspielenMoeglich = $derived(mitArten && art === "audio" && haupt.artZahlen.audio > 0);
  const nurListe = $derived(mitArten && art === "audio");

  function aufDateiwahl(e: Event) {
    const ziel = e.target as HTMLInputElement;
    hochladen(ziel.files, haupt);
    ziel.value = "";
  }

  function zeigeListe() {
    zustand.split = false;
    haupt.ansicht = "liste";
  }

  function zeigeKacheln(g: Kachelgroesse) {
    zustand.split = false;
    haupt.ansicht = "grid";
    haupt.kachelgroesse = g;
  }
</script>

<div class="werkzeuge">
  {#if zustand.navAus}
    <button class="icon-knopf" title="Navigation einblenden" aria-label="Navigation einblenden" onclick={navUmschalten}>
      <i class="fa-solid fa-bars"></i>
    </button>
  {/if}

  {#if istSplit}
    <!-- Anlegen/Hochladen sitzen im Splitscreen je Pane -->
  {:else if haupt.rechte.anlegen}
    <button class="knopf primaer" title="Neuer Ordner" aria-label="Neuer Ordner" onclick={onNeuerOrdner}>
      <i class="fa-solid fa-folder-plus"></i>
    </button>
    <label class="knopf" title="Hochladen" aria-label="Hochladen">
      <i class="fa-solid fa-arrow-up-from-bracket"></i>
      <input type="file" multiple onchange={aufDateiwahl} hidden />
    </label>
  {:else if haupt.bereich === "extern" && haupt.externBrowse}
    <!-- Externe Quellen sind nur lesbar -->
    <button class="knopf" title="Aktualisieren" onclick={() => haupt.ladeExtern()}>
      <i class="fa-solid fa-arrows-rotate"></i> Aktualisieren
    </button>
  {:else if haupt.bereich === "papierkorb" && haupt.eintraege.length > 0}
    <button class="knopf" onclick={onPapierkorbLeeren}>
      <i class="fa-solid fa-trash-can"></i> Papierkorb leeren
    </button>
  {/if}

  {#if mitArten}
    <ArtWahl browser={haupt} />
  {/if}
  {#if diashowMoeglich}
    <button class="knopf" title="Diashow aller Bilder hier" onclick={() => diashowDerFlaeche(haupt)}>
      <i class="fa-solid fa-images"></i> Diashow
    </button>
  {/if}
  {#if abspielenMoeglich}
    <button class="knopf" title="Alle Titel hier nacheinander abspielen" onclick={() => alleAbspielen(haupt)}>
      <i class="fa-solid fa-play"></i> Alle abspielen
    </button>
  {/if}

  <span class="luecke"></span>

  <div class="seg darstellung" role="radiogroup" aria-label="Darstellung">
    <button
      type="button"
      role="radio"
      aria-checked={!istSplit && haupt.zeigtListe}
      class:aktiv={!istSplit && (haupt.ansicht === "liste" || nurListe)}
      title={nurListe ? "Audio zeigt die Titelliste" : "Liste mit Details (Dauer bei Ton und Video)"}
      onclick={zeigeListe}
    >
      <i class="fa-solid fa-list"></i>
    </button>
    <span class="trenner"></span>
    {#each KACHELGROESSEN as g (g.id)}
      <button
        type="button"
        role="radio"
        aria-checked={!istSplit && !nurListe && haupt.ansicht === "grid" && haupt.kachelgroesse === g.id}
        class:aktiv={!istSplit && !nurListe && haupt.ansicht === "grid" && haupt.kachelgroesse === g.id}
        disabled={nurListe}
        title={nurListe ? "Audio zeigt die Titelliste" : g.titel}
        onclick={() => zeigeKacheln(g.id)}
      >
        <i class={g.icon}></i>
      </button>
    {/each}
    {#if haupt.bereich === "dateien"}
      <span class="trenner"></span>
      <button
        type="button"
        role="radio"
        aria-checked={istSplit}
        class:aktiv={istSplit}
        title="Geteilte Ansicht"
        onclick={() => (zustand.split = true)}
      >
        <i class="fa-solid fa-table-columns"></i>
      </button>
    {/if}
  </div>
</div>

<style>
  .werkzeuge {
    flex-wrap: wrap;
    row-gap: var(--a2);
  }
  /* Bricht die Leiste um, bleibt die Darstellung rechts */
  .darstellung {
    margin-left: auto;
  }
</style>

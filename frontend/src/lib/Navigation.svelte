<script lang="ts">
  import { zustand, zeigeDateien, zeigePapierkorb, zeigeExterneQuellen } from "./zustand.svelte";
  import { groesseText } from "./format";

  // Linke Zone: Bereiche. Favoriten und Geteilt sind noch nicht hinterlegt und
  // daher als "bald" gekennzeichnet (kein vorgetaeuschter Inhalt).

  const prozent = $derived(
    zustand.speicher && zustand.speicher.quota
      ? Math.min(100, Math.round((zustand.speicher.benutzt / zustand.speicher.quota) * 100))
      : 0,
  );
</script>

<nav class="nav">
  <div class="nav-titel">Bereiche</div>

  <button class="nav-eintrag" class:aktiv={zustand.bereich === "dateien"} onclick={zeigeDateien}>
    <i class="fa-solid fa-folder"></i> Meine Dateien
  </button>

  <button class="nav-eintrag" disabled title="Bald verfügbar">
    <i class="fa-solid fa-star"></i> Favoriten <span class="bald">bald</span>
  </button>

  <button class="nav-eintrag" disabled title="Bald verfügbar">
    <i class="fa-solid fa-share-nodes"></i> Geteilt <span class="bald">bald</span>
  </button>

  <button
    class="nav-eintrag"
    class:aktiv={zustand.bereich === "extern"}
    onclick={zeigeExterneQuellen}
  >
    <i class="fa-solid fa-folder-tree"></i> Externe Quellen
  </button>

  <button
    class="nav-eintrag"
    class:aktiv={zustand.bereich === "papierkorb"}
    onclick={zeigePapierkorb}
  >
    <i class="fa-solid fa-trash"></i> Papierkorb
  </button>

  {#if zustand.speicher}
    <div class="speicher">
      {#if zustand.speicher.quota}
        {groesseText(zustand.speicher.benutzt)} von {groesseText(zustand.speicher.quota)}
        <div class="balken"><span style="width: {prozent}%"></span></div>
      {:else}
        {groesseText(zustand.speicher.benutzt)} belegt
      {/if}
    </div>
  {/if}
</nav>

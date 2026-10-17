<script lang="ts">
  import type { Knoten } from "./types";
  import { symbol, groesseText, ordnerInhalt } from "./format";
  import BildVorschau from "./medien/BildVorschau.svelte";
  import VideoVorschau from "./medien/VideoVorschau.svelte";
  import AudioVorschau from "./medien/AudioVorschau.svelte";

  interface Props {
    k: Knoten;
    gewaehlt: boolean;
    gezogen: boolean;
    schreibbar: boolean;
    umbenennenAktiv: boolean;
    zielordner: boolean;
    onClick: (e: MouseEvent) => void;
    onDblClick: () => void;
    onBox: (e: MouseEvent) => void;
    onKontext: (e: MouseEvent) => void;
    onDragStart: (e: DragEvent) => void;
    onDragEnd: () => void;
    onUmbenennenFertig: (name: string) => void;
    onUmbenennenAbbruch: () => void;
    onOrdnerDragOver?: (e: DragEvent) => void;
    onOrdnerDragLeave?: () => void;
    onOrdnerDrop?: (e: DragEvent) => void;
    onSpielen?: () => void; // Audio: der Knopf auf dem Cover startet oder pausiert
  }
  let {
    k,
    gewaehlt,
    gezogen,
    schreibbar,
    umbenennenAktiv,
    zielordner,
    onClick,
    onDblClick,
    onBox,
    onKontext,
    onDragStart,
    onDragEnd,
    onUmbenennenFertig,
    onUmbenennenAbbruch,
    onOrdnerDragOver,
    onOrdnerDragLeave,
    onOrdnerDrop,
    onSpielen,
  }: Props = $props();

  const sym = $derived(symbol(k));
  // Vorschau nach Medienart (vom Server); andere Dateien zeigen ihr Symbol.
  const art = $derived(k.typ === "datei" ? (k.medienart ?? null) : null);
  const istOrdnerZiel = $derived(k.typ === "ordner" && schreibbar);
  const metaText = $derived(
    k.typ === "ordner"
      ? ordnerInhalt(k.kinder_anzahl)
      : k.typ === "extern"
        ? "Externe Quelle"
        : k.groesse != null
          ? groesseText(k.groesse)
          : "Datei",
  );

  let entwurf = $state(k.name);
  $effect(() => {
    if (umbenennenAktiv) entwurf = k.name;
  });

  function fokus(el: HTMLInputElement) {
    el.focus();
    const punkt = el.value.lastIndexOf(".");
    if (punkt > 0) el.setSelectionRange(0, punkt);
    else el.select();
  }

  function tasteImFeld(e: KeyboardEvent) {
    if (e.key === "Enter") {
      e.preventDefault();
      onUmbenennenFertig(entwurf);
    } else if (e.key === "Escape") {
      e.preventDefault();
      onUmbenennenAbbruch();
    }
  }
</script>

<div
  class="kachel"
  class:gewaehlt
  class:gezogen
  class:zielordner
  data-id={k.id}
  role="gridcell"
  tabindex="-1"
  draggable={gewaehlt && schreibbar && !umbenennenAktiv}
  ondragstart={(e) => onDragStart(e)}
  ondragend={onDragEnd}
  ondragover={istOrdnerZiel ? onOrdnerDragOver : undefined}
  ondragleave={istOrdnerZiel ? onOrdnerDragLeave : undefined}
  ondrop={istOrdnerZiel ? onOrdnerDrop : undefined}
  onclick={(e) => onClick(e)}
  ondblclick={onDblClick}
  oncontextmenu={(e) => onKontext(e)}
>
  <span
    class="aus-box"
    class:an={gewaehlt}
    role="checkbox"
    aria-checked={gewaehlt}
    tabindex="-1"
    onclick={(e) => {
      e.stopPropagation();
      onBox(e);
    }}
  >
    <i class="fa-solid fa-check"></i>
  </span>

  <div class="vorschau" class:ordner={k.typ !== "datei"} class:hat-vorschau={!!art}>
    {#if art === "bild"}
      <BildVorschau m={k} />
    {:else if art === "video"}
      <VideoVorschau m={k} />
    {:else if art === "audio"}
      <AudioVorschau m={k} spielen={() => onSpielen?.()} />
    {:else}
      <i class="fa-solid {sym.icon}"></i>
    {/if}
  </div>

  {#if umbenennenAktiv}
    <input
      class="umbenennen-feld"
      bind:value={entwurf}
      use:fokus
      onclick={(e) => e.stopPropagation()}
      ondblclick={(e) => e.stopPropagation()}
      onkeydown={tasteImFeld}
      onblur={() => onUmbenennenFertig(entwurf)}
    />
  {:else}
    <div class="k-name-zeile">
      <div class="k-name" title={k.name}>{k.name}</div>
      {#if k.geteilt}
        <i class="geteilt-marke fa-solid fa-share-nodes" title="Mit anderen geteilt" aria-label="Geteilt"></i>
      {/if}
    </div>
  {/if}
  <div class="k-meta">{metaText}</div>
</div>

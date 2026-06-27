<script lang="ts">
  import type { Knoten } from "./types";
  import { symbol, groesseText, datum } from "./format";

  export type RowAktion = "herunterladen" | "umbenennen" | "loeschen" | "wiederherstellen" | "favorit";

  interface Props {
    k: Knoten;
    gewaehlt: boolean;
    gezogen: boolean;
    schreibbar: boolean;
    imPapierkorb: boolean;
    umbenennenAktiv: boolean;
    zielordner: boolean;
    onClick: (e: MouseEvent) => void;
    onDblClick: () => void;
    onBox: (e: MouseEvent) => void;
    onKontext: (e: MouseEvent) => void;
    onDragStart: (e: DragEvent) => void;
    onDragEnd: () => void;
    onAktion: (art: RowAktion) => void;
    onUmbenennenFertig: (name: string) => void;
    onUmbenennenAbbruch: () => void;
    onOrdnerDragOver?: (e: DragEvent) => void;
    onOrdnerDragLeave?: () => void;
    onOrdnerDrop?: (e: DragEvent) => void;
  }
  let {
    k,
    gewaehlt,
    gezogen,
    schreibbar,
    imPapierkorb,
    umbenennenAktiv,
    zielordner,
    onClick,
    onDblClick,
    onBox,
    onKontext,
    onDragStart,
    onDragEnd,
    onAktion,
    onUmbenennenFertig,
    onUmbenennenAbbruch,
    onOrdnerDragOver,
    onOrdnerDragLeave,
    onOrdnerDrop,
  }: Props = $props();

  const sym = $derived(symbol(k));
  const istOrdnerZiel = $derived(k.typ === "ordner" && schreibbar);
  const metaText = $derived(
    k.typ === "ordner"
      ? k.kinder_anzahl == null
        ? "-"
        : k.kinder_anzahl === 0
          ? "Leer"
          : `${k.kinder_anzahl} ${k.kinder_anzahl === 1 ? "Datei" : "Dateien"}`
      : k.typ === "datei" && k.groesse != null
        ? groesseText(k.groesse)
        : "-",
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
  class="zeile"
  class:gewaehlt
  class:gezogen
  class:zielordner
  data-id={k.id}
  role="row"
  tabindex="-1"
  draggable={schreibbar && !umbenennenAktiv}
  ondragstart={(e) => onDragStart(e)}
  ondragend={onDragEnd}
  ondragover={istOrdnerZiel ? onOrdnerDragOver : undefined}
  ondragleave={istOrdnerZiel ? onOrdnerDragLeave : undefined}
  ondrop={istOrdnerZiel ? onOrdnerDrop : undefined}
  onclick={(e) => onClick(e)}
  ondblclick={onDblClick}
  oncontextmenu={(e) => onKontext(e)}
>
  <span class="z-aus">
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
  </span>

  <span class="z-name">
    <i class="sym fa-solid {sym.icon} {sym.klasse}"></i>
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
      <span class="titel">{k.name}</span>
    {/if}
  </span>

  <span class="z-meta">{metaText}</span>
  <span class="z-meta z-geaendert">{datum(k.geaendert_am)}</span>

  <span class="z-akt">
    {#if imPapierkorb}
      <button
        class="icon-knopf"
        title="Wiederherstellen"
        onclick={(e) => {
          e.stopPropagation();
          onAktion("wiederherstellen");
        }}
      >
        <i class="fa-solid fa-rotate-left"></i>
      </button>
    {:else}
      <button
        class="icon-knopf"
        class:fav={k.favorit}
        title={k.favorit ? "Aus Favoriten entfernen" : "Zu Favoriten"}
        onclick={(e) => {
          e.stopPropagation();
          onAktion("favorit");
        }}
      >
        <i class="{k.favorit ? 'fa-solid' : 'fa-regular'} fa-star"></i>
      </button>
      {#if k.typ === "datei"}
        <button
          class="icon-knopf"
          title="Herunterladen"
          onclick={(e) => {
            e.stopPropagation();
            onAktion("herunterladen");
          }}
        >
          <i class="fa-solid fa-download"></i>
        </button>
      {/if}
      {#if schreibbar}
        <button
          class="icon-knopf"
          title="Umbenennen"
          onclick={(e) => {
            e.stopPropagation();
            onAktion("umbenennen");
          }}
        >
          <i class="fa-solid fa-pen"></i>
        </button>
        <button
          class="icon-knopf gefahr"
          title="In den Papierkorb"
          onclick={(e) => {
            e.stopPropagation();
            onAktion("loeschen");
          }}
        >
          <i class="fa-solid fa-trash"></i>
        </button>
      {/if}
    {/if}
  </span>
</div>

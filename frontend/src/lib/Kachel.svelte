<script lang="ts">
  import type { Knoten } from "./types";
  import { symbol, groesseText } from "./format";

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
  }: Props = $props();

  const sym = $derived(symbol(k));
  const istOrdnerZiel = $derived(k.typ === "ordner" && schreibbar);
  const metaText = $derived(
    k.typ === "ordner"
      ? "Ordner"
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

  <div class="vorschau" class:ordner={k.typ !== "datei"}>
    <i class="fa-solid {sym.icon}"></i>
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
    <div class="k-name" title={k.name}>{k.name}</div>
  {/if}
  <div class="k-meta">{metaText}</div>
</div>

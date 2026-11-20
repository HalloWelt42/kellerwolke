<script lang="ts">
  import type { Anfrage, Knoten } from "./types";
  import { symbol, groesseText, datum, ordnerInhalt, rolleText, mitBegleitern } from "./format";
  import { anfrageStand } from "./anfragestand";
  import { player, aktuelleSpur } from "./player.svelte";
  import Dauer from "./medien/Dauer.svelte";
  import { istVerweis, liestInhalt, mitVerweisen, verweiseText } from "./knoten";

  export type RowAktion =
    | "herunterladen"
    | "umbenennen"
    | "loeschen"
    | "wiederherstellen"
    | "endgueltig"
    | "favorit"
    | "original";

  interface Props {
    k: Knoten;
    gewaehlt: boolean;
    gezogen: boolean;
    schreibbar: boolean;
    imPapierkorb: boolean;
    umbenennenAktiv: boolean;
    zielordner: boolean;
    gruppe?: "zu" | "offen" | null; // Hauptdatei mit Begleitern in dieser Liste
    begleiter?: boolean; // steht eingerückt unter seiner Hauptdatei
    anfrage?: Anfrage | null; // offene Anfrage an eine App zu dieser Datei
    nummer?: number | null; // Titelnummer in der Ansicht Audio (statt des Symbols)
    onMedium?: () => void; // Aktion der Art: Bild im Vollbild, Ton und Video abspielen (KW-5)
    onGruppe?: () => void;
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
    gruppe = null,
    begleiter = false,
    anfrage = null,
    nummer = null,
    onMedium,
    onGruppe,
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
  const verweis = $derived(istVerweis(k));
  const metaText = $derived(
    k.typ === "ordner"
      ? ordnerInhalt(k.kinder_anzahl, "-")
      : liestInhalt(k) && k.groesse != null
        ? groesseText(k.groesse)
        : "-",
  );
  const verweisTitel = $derived(
    k.verwaist ? "Das Original gibt es nicht mehr; der Verweis zeigt ins Leere" : `Verweis auf ${k.ziel_name ?? "eine Datei"}`,
  );

  const stand = $derived(anfrage ? anfrageStand(anfrage) : null);

  // Medien bekommen statt des Symbols einen Knopf mit der Aktion ihrer Art; der laufende Titel ist markiert.
  const art = $derived(liestInhalt(k) && !imPapierkorb ? (k.medienart ?? null) : null);
  const spielt = $derived(art === "audio" && aktuelleSpur()?.id === k.id);
  const aktion = $derived(
    art === "bild"
      ? { icon: "fa-expand", titel: "Vollbild" }
      : spielt && player.laeuft
        ? { icon: "fa-pause", titel: "Pause" }
        : { icon: "fa-play", titel: spielt ? "Weiter abspielen" : "Abspielen" },
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

<!-- Symbol der Zeile: Knopf mit der Aktion der Art (Medien) oder das Symbol; ein Verweis trägt dazu den Pfeil -->
{#snippet symbolTeil()}
  {#if art && onMedium}
    <button
      class="sym-knopf art-{art}"
      class:spielt
      title={aktion.titel}
      aria-label="{aktion.titel}: {k.name}"
      onclick={(e) => {
        e.stopPropagation();
        onMedium();
      }}
      ondblclick={(e) => e.stopPropagation()}
    >
      <span class="sk-ruhe">
        {#if nummer}{nummer}{:else}<i class="fa-solid {sym.icon} {sym.klasse}"></i>{/if}
      </span>
      <span class="sk-aktion"><i class="fa-solid {aktion.icon}"></i></span>
    </button>
  {:else}
    <i class="sym fa-solid {sym.icon} {sym.klasse}"></i>
  {/if}
{/snippet}

<div
  class="zeile"
  class:spielt
  class:begleiter
  class:verwaist={verweis && k.verwaist}
  class:gewaehlt
  class:gezogen
  class:zielordner
  data-id={k.id}
  role="row"
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
    {#if verweis}
      <span class="sym-verweis" class:verwaist={k.verwaist} title={verweisTitel}
        >{@render symbolTeil()}<i class="verweis-pfeil fa-solid {k.verwaist ? 'fa-link-slash' : 'fa-share'}"></i></span
      >
    {:else}
      {@render symbolTeil()}
    {/if}
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
      {#if k.geteilt}
        <i class="geteilt-marke fa-solid fa-share-nodes" title="Mit anderen geteilt" aria-label="Geteilt"></i>
      {/if}
      {#if gruppe}
        <button
          class="begleit-knopf"
          class:offen={gruppe === "offen"}
          title={gruppe === "offen" ? "Begleiter ausblenden" : "Begleiter zeigen"}
          aria-expanded={gruppe === "offen"}
          onclick={(e) => {
            e.stopPropagation();
            onGruppe?.();
          }}
          ondblclick={(e) => e.stopPropagation()}
        >
          <i class="fa-solid fa-chevron-right"></i><i class="fa-solid fa-paperclip"></i>
          {k.begleiter_anzahl}
        </button>
      {:else if imPapierkorb && k.begleiter_anzahl}
        <span class="begleit-marke"><i class="fa-solid fa-paperclip"></i> {mitBegleitern(k.begleiter_anzahl)}</span>
      {:else if imPapierkorb && k.haupt_name && k.rolle}
        <span class="begleit-marke" title="Kommt beim Wiederherstellen zurück neben {k.haupt_name}">{rolleText(k.rolle)} zu {k.haupt_name}</span>
      {/if}
      {#if k.rolle && begleiter}
        <span class="rolle-chip">{rolleText(k.rolle)}</span>
      {/if}
      {#if verweis}
        <span class="verweis-chip" class:verwaist={k.verwaist} title={verweisTitel}
          ><i class="fa-solid {k.verwaist ? 'fa-link-slash' : 'fa-share'}"></i><span class="vc-text"
            >{k.verwaist ? "verwaist" : "Verweis"}</span
          ></span
        >
        {#if imPapierkorb && !k.verwaist}
          <span class="verweis-marke">allein gelöscht, das Original bleibt</span>
        {/if}
      {:else if k.verweis_anzahl}
        <span class="verweis-marke" title={imPapierkorb ? "Kommen beim Wiederherstellen mit zurück" : "Verweise auf diese Datei"}
          ><i class="fa-solid fa-share"></i>
          <span class="vm-text">{imPapierkorb ? mitVerweisen(k.verweis_anzahl) : verweiseText(k.verweis_anzahl)}</span></span
        >
      {/if}
      {#if stand}
        <span class="anfrage-pille" class:wartet={stand.wartet} title={stand.titel}>
          <i class={stand.wartet ? "fa-regular fa-clock" : "fa-solid fa-circle-notch fa-spin"}></i>
          <span class="ap-text">{stand.text}</span>
          {stand.zahl}
        </span>
      {/if}
    {/if}
  </span>

  <span class="z-meta z-dauer">
    {#if art === "audio" || art === "video"}<Dauer m={k} {art} />{/if}
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
      <button
        class="icon-knopf gefahr"
        title="Endgültig löschen"
        onclick={(e) => {
          e.stopPropagation();
          onAktion("endgueltig");
        }}
      >
        <i class="fa-solid fa-trash"></i>
      </button>
    {:else if verweis}
      {#if !k.verwaist}
        <button
          class="icon-knopf"
          title="Zum Original"
          onclick={(e) => {
            e.stopPropagation();
            onAktion("original");
          }}
        >
          <i class="fa-solid fa-arrow-right-to-bracket"></i>
        </button>
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
        {#if !k.verwaist}
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
        {/if}
        <button
          class="icon-knopf gefahr"
          title="Verweis in den Papierkorb"
          onclick={(e) => {
            e.stopPropagation();
            onAktion("loeschen");
          }}
        >
          <i class="fa-solid fa-trash"></i>
        </button>
      {/if}
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

<script lang="ts">
  import { untrack } from "svelte";
  import * as api from "../api";
  import { vollansicht, aktuellesVoll, schliesseVollansicht, vollBlaettern } from "../vorschau.svelte";
  import { player, umschalten } from "../player.svelte";
  import { haupt } from "../zustand.svelte";
  import { groesseText } from "../format";
  import { ursache, vollUrl, stromUrl } from "../medien/adressen";
  import { kurzDatum } from "./anzeige";
  import { teilenOderSichern } from "./teilen";
  import { blattOeffnen } from "./mobil.svelte";

  // Vollbild am Telefon: wischen für das nächste, unten Teilen, Stern, Info und
  // Löschen (per Halten). Dieselbe Liste wie die Vollansicht am Rechner.
  const m = $derived(aktuellesVoll());
  const anzahl = $derived(vollansicht.liste.length);
  let fehler = $state("");
  let info = $state(false);

  $effect(() => {
    void m?.id;
    fehler = "";
  });

  // Ein Video öffnen pausiert laufenden Ton - einmal beim Öffnen.
  $effect(() => {
    if (m?.art !== "video") return;
    void m.id;
    untrack(() => {
      if (player.laeuft) umschalten();
    });
  });

  async function nichtGeladen(url: string) {
    fehler = await ursache(url);
  }

  // Wischen: waagerecht mehr als 50 Punkte blättert, senkrecht nach unten schließt.
  let startX = 0;
  let startY = 0;
  function runter(e: PointerEvent) {
    startX = e.clientX;
    startY = e.clientY;
  }
  function hoch(e: PointerEvent) {
    const dx = e.clientX - startX;
    const dy = e.clientY - startY;
    if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy)) vollBlaettern(dx < 0 ? 1 : -1);
    else if (dy > 90 && Math.abs(dy) > Math.abs(dx)) schliesseVollansicht();
  }

  async function sternUmschalten() {
    const e = m;
    if (!e || e.favorit === null) return;
    const neu = !e.favorit;
    try {
      await api.favoritSetzen(e.id, neu);
      e.favorit = neu;
      haupt.aktualisiere();
    } catch {
      // bleibt wie es war
    }
  }

  function loeschen() {
    const e = m;
    if (!e) return;
    blattOeffnen({
      art: "halten",
      knoten: { id: e.id, name: e.name, typ: "datei", medienart: e.art },
      was: "loeschen",
      fertig: () => {
        const i = vollansicht.liste.findIndex((x) => x.id === e.id);
        if (i >= 0) vollansicht.liste.splice(i, 1);
        if (!vollansicht.liste.length) schliesseVollansicht();
        else vollansicht.index = Math.min(vollansicht.index, vollansicht.liste.length - 1);
      },
    });
  }

  function teilen() {
    const e = m;
    if (e) teilenOderSichern({ id: e.id, name: e.name, groesse: e.groesse } as Parameters<typeof teilenOderSichern>[0]);
  }
</script>

{#if m}
  <div class="m-vollbild" role="dialog" aria-modal="true" aria-label={m.name}>
    <div class="m-kopf">
      <button class="m-knopf" aria-label="Schließen" onclick={schliesseVollansicht}><i class="fa-solid fa-xmark"></i></button>
      <h1 style="font-size:17px">
        {m.name}
        <span class="m-unter">{[m.geaendert_am ? kurzDatum(m.geaendert_am) : "", m.groesse != null ? groesseText(m.groesse).replace(".", ",") : ""].filter(Boolean).join(" · ")}</span>
      </h1>
    </div>
    <div class="m-bild" role="presentation" onpointerdown={runter} onpointerup={hoch}>
      {#if fehler}
        <div class="m-bild-fehler"><i class="fa-solid fa-triangle-exclamation"></i>{fehler}</div>
      {:else if m.art === "video"}
        <!-- svelte-ignore a11y_media_has_caption -->
        <video src={stromUrl(m)} controls autoplay playsinline onerror={() => nichtGeladen(stromUrl(m as NonNullable<typeof m>))}></video>
      {:else}
        <img src={vollUrl(m)} alt={m.name} draggable="false" onerror={() => nichtGeladen(vollUrl(m as NonNullable<typeof m>))} />
      {/if}
    </div>
    {#if info}
      <div class="m-info">
        <div><span>Ort</span><span>{m.pfad ? ["Meine Dateien", ...m.pfad.map((p) => p.name)].join(" / ") : "-"}</span></div>
        <div><span>Größe</span><span>{m.groesse != null ? groesseText(m.groesse).replace(".", ",") : "-"}</span></div>
        <div><span>Geändert</span><span>{m.geaendert_am ? kurzDatum(m.geaendert_am) : "-"}</span></div>
      </div>
    {/if}
    {#if anzahl > 1}<div class="m-punkte">{vollansicht.index + 1} von {anzahl}</div>{/if}
    <div class="m-leiste">
      <button class="m-knopf" aria-label="Teilen oder sichern" onclick={teilen}><i class="fa-solid fa-arrow-up-from-bracket"></i></button>
      {#if m.favorit !== null}
        <button class="m-knopf" aria-label={m.favorit ? "Aus Favoriten nehmen" : "Zu Favoriten"} onclick={sternUmschalten}>
          <i class="fa-{m.favorit ? 'solid' : 'regular'} fa-star" style={m.favorit ? "color:#f0b34a" : ""}></i>
        </button>
      {/if}
      <button class="m-knopf" aria-label="Informationen" aria-pressed={info} onclick={() => (info = !info)}><i class="fa-solid fa-circle-info"></i></button>
      {#if m.eigen}
        <button class="m-knopf" aria-label="Löschen" onclick={loeschen}><i class="fa-solid fa-trash"></i></button>
      {/if}
    </div>
  </div>
{/if}

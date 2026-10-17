<script lang="ts">
  import { onMount } from "svelte";
  import * as api from "../api";
  import { auth, abmelden } from "../auth.svelte";
  import { thema } from "../thema.svelte";
  import { zustand, ladeSpeicher } from "../zustand.svelte";
  import { groesseText } from "../format";
  import type { Geraet } from "../types";
  import { blattOeffnen, zeigeSeite } from "./mobil.svelte";

  // Mehr: Geteiltes, Papierkorb, Speicher und Konto. Was nur am Rechner Sinn
  // ergibt (Verwaltung, Zugänge, Geräte koppeln, geteilte Ansicht), steht hier nicht. Ein gekoppeltes Gerät
  // zeigt sich selbst und trennt sich statt abzumelden.
  let geteilt = $state<number | null>(null);
  let papierkorb = $state<number | null>(null);
  let geraet = $state<Geraet | null>(null); // gesetzt, wenn dieses Gerät gekoppelt ist (statt mit Passwort angemeldet)

  onMount(async () => {
    ladeSpeicher();
    try {
      const [g, p] = await Promise.all([api.geteilt(), api.papierkorb()]);
      geteilt = g.length;
      papierkorb = p.length;
    } catch {
      // Zahlen sind Zusatz
    }
    try {
      geraet = await api.diesesGeraet();
    } catch {
      geraet = null; // mit Passwort angemeldet
    }
  });

  const s = $derived(zustand.speicher);
  const anteil = $derived(s && s.gesamt ? Math.min(100, (s.benutzt / s.gesamt) * 100) : 0);
  const themaText = $derived(thema.wahl === "system" ? "wie das Telefon" : thema.wahl === "dunkel" ? "dunkel" : "hell");
  const seit = (iso: string) => new Date(iso).toLocaleDateString("de-DE");
  const anzahl = (n: number | null, eins: string, mehr: string) => (n === null ? "" : n === 1 ? `1 ${eins}` : `${n} ${mehr}`);
</script>

<div class="m-liste" style="margin-top:6px">
  <button class="m-zeile" onclick={() => zeigeSeite("geteilt")}>
    <i class="fa-solid fa-user-group m-symbol"></i>
    <span class="m-text"><span class="m-name" style="display:block">Mit mir geteilt</span><span class="m-meta" style="display:block">{anzahl(geteilt, "Eintrag", "Einträge")}</span></span>
    <span class="m-mehr"><i class="fa-solid fa-chevron-right"></i></span>
  </button>
  <button class="m-zeile" onclick={() => zeigeSeite("papierkorb")}>
    <i class="fa-solid fa-trash-can m-symbol"></i>
    <span class="m-text"><span class="m-name" style="display:block">Papierkorb</span><span class="m-meta" style="display:block">{anzahl(papierkorb, "Eintrag", "Einträge")}</span></span>
    <span class="m-mehr"><i class="fa-solid fa-chevron-right"></i></span>
  </button>
</div>

<div class="m-gruppe">Speicher</div>
<div class="m-liste">
  <div class="m-zeile" style="cursor:default">
    <i class="fa-solid fa-hard-drive m-symbol"></i>
    <div class="m-text">
      {#if s && s.verfuegbar === false}
        <div class="m-name">Speicher gerade nicht erreichbar</div>
        <div class="m-meta">Es geht nichts verloren; sobald das Laufwerk da ist, geht es weiter.</div>
      {:else if s}
        <div class="m-name">{groesseText(s.benutzt).replace(".", ",")} belegt</div>
        <div class="m-fortschritt"><span style="width: {anteil}%"></span></div>
        {#if s.frei != null}<div class="m-meta" style="margin-top:6px">{groesseText(s.frei).replace(".", ",")} frei auf dem Server</div>{/if}
      {:else}
        <div class="m-name">-</div>
      {/if}
    </div>
  </div>
</div>

<div class="m-gruppe">Konto</div>
<div class="m-liste">
  <button class="m-zeile" onclick={() => blattOeffnen({ art: "thema" })}>
    <i class="fa-solid fa-circle-half-stroke m-symbol"></i>
    <span class="m-text"><span class="m-name" style="display:block">Thema</span><span class="m-meta" style="display:block">{themaText}</span></span>
  </button>
  {#if geraet}
    <div class="m-zeile" style="cursor:default">
      <i class="fa-solid fa-mobile-screen m-symbol"></i>
      <span class="m-text">
        <span class="m-name" style="display:block">{geraet.name}<span class="m-geraet-marke">dieses Gerät</span></span>
        <span class="m-meta" style="display:block">gekoppelt seit {seit(geraet.gekoppelt_am)} · Konto {auth.benutzer?.name ?? ""}</span>
      </span>
    </div>
    <button class="m-zeile m-gefahr" onclick={abmelden}>
      <i class="fa-solid fa-link-slash m-symbol"></i>
      <span class="m-text"><span class="m-name" style="display:block">Gerät trennen</span><span class="m-meta" style="display:block">meldet ab; zum Wiederkommen neu koppeln</span></span>
    </button>
  {:else}
    <button class="m-zeile" onclick={abmelden}>
      <i class="fa-solid fa-right-from-bracket m-symbol"></i>
      <span class="m-text"><span class="m-name" style="display:block">Abmelden</span><span class="m-meta" style="display:block">{auth.benutzer?.name ?? ""}</span></span>
    </button>
  {/if}
</div>
<p class="m-fusszeile">
  Verwaltung, externe Quellen, Zugänge für Apps, Geräte und die geteilte Ansicht gibt es am Rechner.
  {#if zustand.version}<br />Kellerwolke {zustand.version}{/if}
</p>

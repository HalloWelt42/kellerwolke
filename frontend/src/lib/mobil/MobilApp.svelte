<script lang="ts">
  import "./mobil.css";
  import { onMount } from "svelte";
  import * as api from "../api";
  import { haupt, zustand } from "../zustand.svelte";
  import { fassung } from "../fassung.svelte";
  import { verbindung } from "../verbindung.svelte";
  import { vollansichtOffen } from "../vorschau.svelte";
  import { knotenOeffnen } from "../medien/oeffnen";
  import { thema, themaWaehlen, type ThemaWahl } from "../thema.svelte";
  import type { SortKey } from "../browser.svelte";
  import type { Knoten } from "../types";
  import { mobil, zeigeReiter, zurueck, sucheBeenden, blattOeffnen, blattSchliessen, type MobilReiter } from "./mobil.svelte";
  import Blatt from "./Blatt.svelte";
  import MobilListe from "./MobilListe.svelte";
  import MobilAktionen from "./MobilAktionen.svelte";
  import MobilHalten from "./MobilHalten.svelte";
  import MobilEingabe from "./MobilEingabe.svelte";
  import MobilHochladen from "./MobilHochladen.svelte";
  import MobilMedien from "./MobilMedien.svelte";
  import MobilMehr from "./MobilMehr.svelte";
  import MobilVollbild from "./MobilVollbild.svelte";
  import MiniSpieler from "./MiniSpieler.svelte";

  // Schale der Telefon-Oberfläche (Entwurf mockups/mobil.html): Kopf je Ort,
  // Bänder für Verbindung, Speicher und Meldungen, Inhalt, Schwebeknopf,
  // Mini-Spieler, Reiter und das Blatt von unten.
  const REITER: { id: MobilReiter; label: string; icon: string }[] = [
    { id: "dateien", label: "Dateien", icon: "fa-folder" },
    { id: "medien", label: "Medien", icon: "fa-images" },
    { id: "favoriten", label: "Favoriten", icon: "fa-star" },
    { id: "mehr", label: "Mehr", icon: "fa-ellipsis" },
  ];

  // Beim Wechsel vom Rechner aufs Telefon (oder Drehen) zum Bereich der Fläche passend aufsetzen.
  onMount(() => {
    const b = haupt.bereich;
    if (b === "favoriten") mobil.reiter = "favoriten";
    else if (b === "geteilt" || b === "papierkorb") {
      mobil.reiter = "mehr";
      mobil.seite = b;
    } else if (b !== "dateien" && b !== "suche") {
      zeigeReiter("dateien");
    }
  });

  // Was der Kopf zeigt.
  const kopf = $derived.by((): { titel: string; unter: string; zurueck: boolean } => {
    if (mobil.seite === "suche") return { titel: "Suche", unter: "", zurueck: true };
    if (mobil.seite === "geteilt") {
      const p = haupt.geteiltPfad;
      return { titel: p.length ? p[p.length - 1].name : "Mit mir geteilt", unter: p.length ? "Mit mir geteilt" : "", zurueck: true };
    }
    if (mobil.seite === "papierkorb") return { titel: "Papierkorb", unter: "", zurueck: true };
    if (mobil.reiter === "dateien") {
      const p = haupt.pfad;
      return { titel: p[p.length - 1].name, unter: p.length > 1 ? p[p.length - 2].name : "", zurueck: p.length > 1 };
    }
    return { titel: REITER.find((r) => r.id === mobil.reiter)?.label ?? "", unter: "", zurueck: false };
  });

  const zeigtListe = $derived(mobil.seite !== null || mobil.reiter === "dateien" || mobil.reiter === "favoriten");
  const mitPlus = $derived(
    mobil.reiter === "dateien" && !mobil.seite && haupt.rechte.anlegen && !haupt.verschiebeIds && verbindung.ok,
  );
  const mitSortieren = $derived(zeigtListe && mobil.seite !== "suche");

  // --- Suche: erst mit "Suchen" auf der Tastatur ---
  let suchtext = $state("");
  let gesucht = $state(false);
  function sucheOeffnen() {
    suchtext = "";
    gesucht = false;
    mobil.blatt = null;
    mobil.seite = "suche";
  }
  function suchen(e: Event) {
    e.preventDefault();
    const q = suchtext.trim();
    if (!q) return;
    (document.activeElement as HTMLElement | null)?.blur(); // Tastatur weg
    gesucht = true;
    haupt.starteSuche(q);
  }
  function fokus(el: HTMLInputElement) {
    el.focus();
  }

  // --- Öffnen: Ordner hinein, Medien zeigen oder spielen, sonst die Datei holen ---
  function oeffnen(k: Knoten) {
    if (haupt.bereich === "papierkorb") {
      blattOeffnen({ art: "aktionen", knoten: k });
      return;
    }
    if (k.typ !== "datei") {
      const ausSucheOderFavoriten = haupt.bereich === "suche" || haupt.bereich === "favoriten";
      haupt.oeffnen(k);
      if (ausSucheOderFavoriten && k.typ === "ordner") {
        mobil.seite = null;
        mobil.reiter = "dateien";
      }
      return;
    }
    if (!knotenOeffnen(haupt, k)) api.herunterladen(k);
  }

  // --- Blätter ---
  async function umbenennen(k: Knoten, name: string): Promise<string | null> {
    try {
      await api.umbenennen(k.id, name);
    } catch (f) {
      return (f as Error).message;
    }
    blattSchliessen();
    haupt.aktualisiere();
    return null;
  }
  async function ordnerAnlegen(name: string): Promise<string | null> {
    try {
      await api.ordnerAnlegen(name, haupt.aktuellerOrdner);
    } catch (f) {
      return (f as Error).message;
    }
    blattSchliessen();
    haupt.aktualisiere();
    return null;
  }
  const SORTEN: { key: SortKey; label: string; icon: string }[] = [
    { key: "name", label: "Name", icon: "fa-arrow-down-a-z" },
    { key: "geaendert", label: "Geändert", icon: "fa-clock" },
    { key: "groesse", label: "Größe", icon: "fa-weight-hanging" },
  ];
  const THEMEN: { wahl: ThemaWahl; label: string; icon: string }[] = [
    { wahl: "system", label: "Wie das Telefon", icon: "fa-mobile-screen" },
    { wahl: "hell", label: "Hell", icon: "fa-sun" },
    { wahl: "dunkel", label: "Dunkel", icon: "fa-moon" },
  ];

  const uploadsLaufen = $derived(zustand.uploads.filter((u) => u.status === "wartet" || u.status === "laeuft").length);
  const uploadsFertig = $derived(zustand.uploads.filter((u) => u.status === "fertig").length);
  const leerText = $derived(
    haupt.bereich === "papierkorb" ? "Der Papierkorb ist leer"
      : haupt.bereich === "favoriten" ? "Noch keine Favoriten"
        : haupt.bereich === "geteilt" ? (haupt.geteiltPfad.length ? "Dieser Ordner ist leer" : "Nichts mit dir geteilt")
          : haupt.bereich === "suche" ? "Nichts gefunden"
            : "Dieser Ordner ist leer",
  );
</script>

<div class="mobil">
  <!-- Kopf -->
  <div class="m-kopf">
    {#if kopf.zurueck}
      <button class="m-knopf" aria-label="Zurück" onclick={() => (mobil.seite === "suche" ? sucheBeenden() : zurueck())}><i class="fa-solid fa-chevron-left"></i></button>
    {/if}
    <h1 class:ohne-zurueck={!kopf.zurueck}>{kopf.titel}{#if kopf.unter}<span class="m-unter">{kopf.unter}</span>{/if}</h1>
    {#if mobil.reiter === "medien" && !mobil.seite}
      <button class="m-knopf" aria-label="Suchen" onclick={sucheOeffnen}><i class="fa-solid fa-magnifying-glass"></i></button>
    {/if}
    {#if mitSortieren}
      <button class="m-knopf" aria-label="Sortieren" onclick={() => blattOeffnen({ art: "sortieren" })}><i class="fa-solid fa-arrow-down-a-z"></i></button>
    {/if}
  </div>

  {#if mobil.seite === "suche"}
    <form class="m-suche aktiv" onsubmit={suchen}>
      <i class="fa-solid fa-magnifying-glass"></i>
      <input type="search" enterkeyhint="search" placeholder="In allen Dateien suchen" bind:value={suchtext} use:fokus />
      {#if suchtext}
        <button type="button" class="m-mehr" style="width:32px;height:32px" aria-label="Leeren" onclick={() => (suchtext = "")}><i class="fa-solid fa-circle-xmark"></i></button>
      {/if}
    </form>
  {:else if (mobil.reiter === "dateien" || mobil.reiter === "favoriten") && !mobil.seite}
    <button class="m-suche" onclick={sucheOeffnen}><i class="fa-solid fa-magnifying-glass"></i> In allen Dateien suchen</button>
  {/if}

  <!-- Bänder -->
  {#if fassung.neu}
    <div class="m-band" role="alert">
      <i class="fa-solid fa-rotate"></i><span>Neue Fassung {fassung.neu}; lädt beim nächsten Wechsel von selbst</span>
      <button aria-label="Jetzt neu laden" onclick={() => location.reload()}><i class="fa-solid fa-rotate"></i></button>
    </div>
  {/if}
  {#if !verbindung.ok}
    <div class="m-band" role="alert"><i class="fa-solid fa-wifi"></i><span>Keine Verbindung zur Kellerwolke</span></div>
  {:else if zustand.speicher?.verfuegbar === false}
    <div class="m-band" role="alert"><i class="fa-solid fa-triangle-exclamation"></i><span>Speicher nicht verfügbar - es geht nichts verloren</span></div>
  {/if}
  {#if haupt.fehler && zeigtListe}
    <div class="m-band" role="alert">
      <i class="fa-solid fa-circle-exclamation"></i><span>{haupt.fehler}</span>
      <button aria-label="Meldung schließen" onclick={() => haupt.fehlerSchliessen()}><i class="fa-solid fa-xmark"></i></button>
    </div>
  {/if}

  <!-- Inhalt -->
  <div class="m-rahmen">
    <div class="m-inhalt">
      {#if mobil.reiter === "medien" && !mobil.seite}
        <MobilMedien />
      {:else if mobil.reiter === "mehr" && !mobil.seite}
        <MobilMehr />
      {:else if mobil.seite === "suche" && !gesucht}
        <div class="m-leer"><i class="fa-solid fa-magnifying-glass"></i><p>Sucht in Namen und, wo lesbar, im Inhalt aller eigenen Dateien.</p></div>
      {:else if !verbindung.ok && haupt.sichtbar.length === 0}
        <div class="m-leer">
          <i class="fa-solid fa-cloud"></i>
          <h2>Gerade nicht erreichbar</h2>
          <p>Bist du im Heimnetz? Nichts ist verloren; sobald die Verbindung steht, geht es weiter.</p>
          <button class="m-wieder" onclick={() => haupt.aktualisiere()}><i class="fa-solid fa-rotate"></i> Erneut versuchen</button>
        </div>
      {:else if haupt.laden}
        <div class="m-leer"><i class="fa-solid fa-circle-notch fa-spin"></i></div>
      {:else if haupt.sichtbar.length === 0}
        <div class="m-leer"><i class="fa-regular fa-folder-open"></i><h2>{leerText}</h2>{#if mitPlus}<p>Mit dem Plus lädst du Fotos und Dateien hoch.</p>{/if}</div>
      {:else}
        <MobilListe browser={haupt} {oeffnen} aktionen={(k) => blattOeffnen({ art: "aktionen", knoten: k })} mitOrt={haupt.bereich === "suche"} />
      {/if}
    </div>
    {#if mitPlus}
      <button class="m-plus" aria-label="Hochladen oder Ordner anlegen" onclick={() => blattOeffnen({ art: "hochladen" })}><i class="fa-solid fa-plus"></i></button>
    {/if}
  </div>

  {#if haupt.verschiebeIds}
    {@const n = haupt.verschiebeIds.length}
    <div class="m-verschieben">
      <span>{n === 1 ? "1 Objekt" : `${n} Objekte`} verschieben: Zielordner öffnen</span>
      <button class="m-pille still" onclick={() => haupt.verschiebenAbbrechen()}>Abbrechen</button>
      <button class="m-pille primaer" disabled={!haupt.istSchreibbar || mobil.reiter !== "dateien" || !!mobil.seite} onclick={() => haupt.verschiebenHierher()}>Hierher</button>
    </div>
  {/if}

  {#if uploadsLaufen && mobil.blatt?.art !== "hochladen"}
    <button class="m-upload-band" onclick={() => blattOeffnen({ art: "hochladen" })}>
      <i class="fa-solid fa-arrow-up-from-bracket" style="color:var(--m-akzent)"></i>
      <span class="m-text">Lädt hoch: {uploadsFertig} von {zustand.uploads.length}</span>
      <i class="fa-solid fa-chevron-up" style="color:var(--m-text-3)"></i>
    </button>
  {/if}

  <MiniSpieler />

  <nav class="m-tabs">
    {#each REITER as r (r.id)}
      <button class="m-tab" class:aktiv={mobil.reiter === r.id && !mobil.seite} aria-current={mobil.reiter === r.id && !mobil.seite ? "page" : undefined} onclick={() => zeigeReiter(r.id)}>
        <i class="fa-solid {r.icon}"></i>{r.label}
      </button>
    {/each}
  </nav>

  {#if vollansichtOffen()}
    <MobilVollbild />
  {/if}

  {#if mobil.blatt}
    {@const b = mobil.blatt}
    <Blatt schliessen={blattSchliessen}>
      {#if b.art === "aktionen"}
        <MobilAktionen knoten={b.knoten} {oeffnen} />
      {:else if b.art === "halten"}
        <MobilHalten knoten={b.knoten} was={b.was} fertig={b.fertig} />
      {:else if b.art === "hochladen"}
        <MobilHochladen />
      {:else if b.art === "umbenennen"}
        <MobilEingabe titel="Umbenennen" start={b.knoten.name} knopf="Speichern" speichern={(n) => umbenennen(b.knoten, n)} abbrechen={blattSchliessen} />
      {:else if b.art === "ordner"}
        <MobilEingabe titel="Neuer Ordner" knopf="Anlegen" speichern={ordnerAnlegen} abbrechen={blattSchliessen} />
      {:else if b.art === "sortieren"}
        <p class="m-blatt-titel">Sortieren</p>
        {#each SORTEN as s (s.key)}
          <button class="m-aktion" class:an={haupt.sortKey === s.key} onclick={() => haupt.setzeSortierung(s.key)}>
            <i class="fa-solid {s.icon}"></i> {s.label}
            {#if haupt.sortKey === s.key}<span class="m-hinweis">{haupt.sortRichtung === "auf" ? "aufsteigend" : "absteigend"}</span>{/if}
          </button>
        {/each}
      {:else if b.art === "thema"}
        <p class="m-blatt-titel">Thema</p>
        {#each THEMEN as t (t.wahl)}
          <button class="m-aktion" class:an={thema.wahl === t.wahl} onclick={() => { themaWaehlen(t.wahl); blattSchliessen(); }}>
            <i class="fa-solid {t.icon}"></i> {t.label}{#if thema.wahl === t.wahl}<span class="m-hinweis"><i class="fa-solid fa-check"></i></span>{/if}
          </button>
        {/each}
      {/if}
    </Blatt>
  {/if}
</div>

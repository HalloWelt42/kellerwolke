<script lang="ts">
  import { onMount } from "svelte";
  import { auth, ladeStatus, abmelden } from "./lib/auth.svelte";
  import { thema, themaUmschalten } from "./lib/thema.svelte";
  import {
    zustand,
    haupt,
    leerePapierkorb,
    ladeVersion,
    starteLiveAbgleich,
    stoppeLiveAbgleich,
    vorgaengeUmschalten,
    hochladen,
    strukturHochladen,
  } from "./lib/zustand.svelte";
  import Login from "./lib/Login.svelte";
  import Navigation from "./lib/Navigation.svelte";
  import Werkzeugleiste from "./lib/Werkzeugleiste.svelte";
  import Breadcrumb from "./lib/Breadcrumb.svelte";
  import Dateiliste from "./lib/Dateiliste.svelte";
  import Splitscreen from "./lib/Splitscreen.svelte";
  import DetailPane from "./lib/DetailPane.svelte";
  import Einstellungen from "./lib/Einstellungen.svelte";
  import Vorgaenge from "./lib/Vorgaenge.svelte";
  import UploadKarte from "./lib/UploadKarte.svelte";
  import Teilen from "./lib/Teilen.svelte";
  import Modal from "./lib/Modal.svelte";
  import Logo from "./lib/Logo.svelte";
  import AppLeiste from "./lib/AppLeiste.svelte";
  import PlayerLeiste from "./lib/PlayerLeiste.svelte";
  import { aktuelleSpur } from "./lib/player.svelte";
  import {
    aktiveApp,
    appZustand,
    ladeAktiveApps,
    waehleApp,
    meldePluginDefekt,
    vollansichtFuer,
    DEFAULT_APP_ID,
  } from "./plugins/registry.svelte";
  import { vorschauZustand, schliesseVollansicht } from "./lib/vorschau.svelte";
  import type { Knoten } from "./lib/types";

  let verwaltungOffen = $state(false);
  let teilenKnoten = $state<Knoten | null>(null);
  let endgueltigKnoten = $state<Knoten | null>(null);
  let nutzerMenuOffen = $state(false);
  let neuerOrdnerOffen = $state(false);
  let papierkorbLeerenOffen = $state(false);
  let ordnerName = $state("");
  let initialGeladen = $state(false);

  onMount(ladeStatus);

  $effect(() => {
    if (auth.angemeldet && !initialGeladen) {
      initialGeladen = true;
      haupt.zeigeDateien();
      ladeVersion();
      ladeAktiveApps();
      starteLiveAbgleich();
    }
    if (!auth.angemeldet) {
      initialGeladen = false;
      stoppeLiveAbgleich();
    }
  });

  const aktuelleApp = $derived(aktiveApp());
  const istDefaultApp = $derived(aktuelleApp.id === DEFAULT_APP_ID);

  // Selbstschutz: rendert eine Plugin-App fehlerhaft, wird sie nach kurzer Frist
  // automatisch deaktiviert, damit sie die App nicht dauerhaft blockiert. Ein
  // "Erneut versuchen" bricht die Frist ab.
  let pluginAbschaltTimer: ReturnType<typeof setTimeout> | null = null;
  function pluginFehler(id: string, e: unknown) {
    console.error("Plugin-Fehler:", id, e);
    if (pluginAbschaltTimer) clearTimeout(pluginAbschaltTimer);
    pluginAbschaltTimer = setTimeout(
      () => meldePluginDefekt(id, e instanceof Error ? e.message : String(e)),
      8000,
    );
  }
  function pluginErneut(reset: () => void) {
    if (pluginAbschaltTimer) clearTimeout(pluginAbschaltTimer);
    pluginAbschaltTimer = null;
    reset();
  }
  // Erlaubt die aktive App den aktuellen Bereich? Sonst zurueck auf Dateien.
  $effect(() => {
    const erlaubt = aktuelleApp.bereiche;
    if (!istDefaultApp && erlaubt && !erlaubt.includes(haupt.bereich)) {
      waehleApp(DEFAULT_APP_ID);
    }
  });

  const istSplit = $derived(zustand.split && haupt.bereich === "dateien" && istDefaultApp);
  const mitDetail = $derived(
    istDefaultApp && haupt.detail !== null && haupt.auswahl.anzahl <= 1 && !istSplit,
  );
  const avatarText = $derived((auth.benutzer?.name ?? "?").slice(0, 1).toUpperCase());
  const laufendeVorgaenge = $derived(zustand.vorgaenge.filter((v) => v.status === "laeuft").length);

  function suchen(e: Event) {
    e.preventDefault();
    haupt.starteSuche(haupt.suchbegriff);
  }

  function ordnerAnlegenBestaetigen() {
    const name = ordnerName.trim();
    if (!name) return;
    haupt.ordnerAnlegen(name);
    ordnerName = "";
    neuerOrdnerOffen = false;
  }

  function fokus(el: HTMLInputElement) {
    el.focus();
  }

  // --- Globales Drag-and-drop: Dateien lassen sich ueberall in der App ablegen
  // (egal welche Ansicht/App aktiv ist) und landen im aktuellen Ordner. ---
  let zieheDatei = $state(false);
  let ziehZaehler = 0; // dragenter/leave-Zaehler gegen Flackern beim Ueberfahren von Kindelementen

  function hatDateien(e: DragEvent): boolean {
    return Array.from(e.dataTransfer?.types ?? []).includes("Files");
  }
  function aufDragEnter(e: DragEvent) {
    if (!auth.angemeldet || verwaltungOffen || !hatDateien(e)) return;
    e.preventDefault();
    ziehZaehler++;
    zieheDatei = true;
  }
  function aufDragOver(e: DragEvent) {
    if (!auth.angemeldet || verwaltungOffen || !hatDateien(e)) return;
    e.preventDefault(); // erlaubt das Ablegen ueberall im Fenster
  }
  function aufDragLeave(e: DragEvent) {
    if (!hatDateien(e)) return;
    ziehZaehler--;
    if (ziehZaehler <= 0) { ziehZaehler = 0; zieheDatei = false; }
  }
  function aufDrop(e: DragEvent) {
    ziehZaehler = 0;
    zieheDatei = false;
    if (!auth.angemeldet || verwaltungOffen || !hatDateien(e)) return;
    e.preventDefault();
    // Ganze Ordner? Eintraege synchron einsammeln (dataTransfer gilt nur waehrend
    // des Ereignisses); enthaelt die Ablage einen Ordner, Struktur erhalten.
    const posten = e.dataTransfer?.items;
    if (posten && posten.length && typeof posten[0].webkitGetAsEntry === "function") {
      const eintraege: FileSystemEntry[] = [];
      for (const p of Array.from(posten)) {
        const en = p.webkitGetAsEntry?.();
        if (en) eintraege.push(en);
      }
      if (eintraege.some((en) => en.isDirectory)) {
        strukturHochladen(eintraege);
        return;
      }
    }
    const dateien = e.dataTransfer?.files;
    if (dateien && dateien.length) hochladen(dateien);
  }
</script>

<svelte:window
  ondragenter={aufDragEnter}
  ondragover={aufDragOver}
  ondragleave={aufDragLeave}
  ondrop={aufDrop}
/>

{#if !auth.geladen}
  <div class="start-laden"><i class="fa-solid fa-cloud fa-beat-fade"></i></div>
{:else if !auth.angemeldet}
  <Login />
{:else if verwaltungOffen}
  <Einstellungen schliessen={() => (verwaltungOffen = false)} />
{:else}
  {#if zieheDatei}
    <div class="global-drop" role="presentation">
      <div class="global-drop-karte">
        <i class="fa-solid fa-cloud-arrow-up"></i>
        <strong>Dateien und Ordner hier ablegen</strong>
        <span>Sie landen im aktuellen Ordner - Ordner mit ihrer Struktur.</span>
      </div>
    </div>
  {/if}
  <div class="app" class:mit-detail={mitDetail} class:nav-aus={zustand.navAus} class:mit-player={!!aktuelleSpur()}>
    <header class="kopf">
      <div class="marke"><Logo size={22} /> Kellerwolke</div>
      <form class="kopf-suche" onsubmit={suchen}>
        <i class="fa-solid fa-magnifying-glass"></i>
        <input type="text" placeholder="In allen Dateien suchen ..." bind:value={haupt.suchbegriff} />
        {#if haupt.bereich === "suche"}
          <button
            type="button"
            class="icon-knopf"
            title="Suche schließen"
            aria-label="Suche schließen"
            onclick={() => haupt.zeigeDateien()}
          >
            <i class="fa-solid fa-xmark"></i>
          </button>
        {/if}
      </form>
      <div class="kopf-rechts">
        <button
          class="icon-knopf kopf-knopf"
          title="Vorgänge"
          aria-label="Vorgänge"
          onclick={vorgaengeUmschalten}
        >
          <i class="fa-solid fa-list-check"></i>
          {#if laufendeVorgaenge > 0}
            <span class="badge">{laufendeVorgaenge}</span>
          {/if}
        </button>
        <div class="nutzer-bereich">
          <button class="nutzer-chip" onclick={() => (nutzerMenuOffen = !nutzerMenuOffen)}>
            <span class="avatar">{avatarText}</span>
            {auth.benutzer?.name}
            <i class="fa-solid fa-chevron-down pfeil"></i>
          </button>
          {#if nutzerMenuOffen}
            <div class="nutzer-menu-hg" role="presentation" onclick={() => (nutzerMenuOffen = false)}></div>
            <div class="nutzer-menu" role="menu">
              <button role="menuitem" onclick={() => { themaUmschalten(); }}>
                <i class="fa-solid {thema.aktuell === 'hell' ? 'fa-moon' : 'fa-sun'}"></i>
                {thema.aktuell === "hell" ? "Dunkles Thema" : "Helles Thema"}
              </button>
              {#if auth.benutzer?.rolle === "admin"}
                <button role="menuitem" onclick={() => { nutzerMenuOffen = false; verwaltungOffen = true; }}>
                  <i class="fa-solid fa-gear"></i> Verwaltung
                </button>
              {/if}
              <div class="ktrenner"></div>
              <button role="menuitem" onclick={() => { nutzerMenuOffen = false; abmelden(); }}>
                <i class="fa-solid fa-right-from-bracket"></i> Abmelden
              </button>
            </div>
          {/if}
        </div>
      </div>
    </header>

    <Navigation />

    <section class="inhalt">
      {#if zustand.speicher?.verfuegbar === false}
        <div class="speicher-warnung" role="alert">
          <i class="fa-solid fa-triangle-exclamation"></i>
          <span>
            <strong>Speicher nicht verfügbar.</strong>
            Das Laufwerk ist gerade nicht erreichbar - Hoch- und Herunterladen
            pausieren, bis es wieder da ist. Es geht nichts verloren.
          </span>
        </div>
      {/if}
      <AppLeiste />
      {#if istDefaultApp}
        <Werkzeugleiste
          onNeuerOrdner={() => (neuerOrdnerOffen = true)}
          onPapierkorbLeeren={() => (papierkorbLeerenOffen = true)}
        />
        {#if istSplit}
          <Splitscreen
            onTeilen={(k) => (teilenKnoten = k)}
            onEndgueltig={(k) => (endgueltigKnoten = k)}
          />
        {:else}
          <Breadcrumb browser={haupt} />
          {#if haupt.fehler}
            <div class="fehlerstreifen">{haupt.fehler}</div>
          {/if}
          <Dateiliste
            browser={haupt}
            onTeilen={(k) => (teilenKnoten = k)}
            onEndgueltig={(k) => (endgueltigKnoten = k)}
          />
        {/if}
      {:else}
        {@const PluginAnsicht = aktuelleApp.ansicht}
        <Breadcrumb browser={haupt} />
        {#if haupt.fehler}
          <div class="fehlerstreifen">{haupt.fehler}</div>
        {/if}
        <svelte:boundary onerror={(e) => pluginFehler(aktuelleApp.id, e)}>
          <PluginAnsicht browser={haupt} />
          {#snippet failed(error, reset)}
            <div class="plugin-fehler" role="alert">
              <i class="fa-solid fa-triangle-exclamation"></i>
              <h3>Die App "{aktuelleApp.label}" ist auf einen Fehler gestoßen</h3>
              <p>Der Rest von Kellerwolke läuft normal weiter. Bleibt der Fehler, wird die App gleich automatisch deaktiviert.</p>
              <pre>{(error as Error)?.message ?? String(error)}</pre>
              <div class="pf-knoepfe">
                <button class="knopf" onclick={() => pluginErneut(reset)}>Erneut versuchen</button>
                <button class="knopf" onclick={() => meldePluginDefekt(aktuelleApp.id, (error as Error)?.message ?? String(error))}>Jetzt deaktivieren</button>
                <button class="knopf primaer" onclick={() => waehleApp(DEFAULT_APP_ID)}>Zu den Dateien</button>
              </div>
            </div>
          {/snippet}
        </svelte:boundary>
      {/if}
    </section>

    {#if mitDetail && haupt.detail}
      <DetailPane k={haupt.detail} onTeilen={(k) => (teilenKnoten = k)} />
    {/if}

    <PlayerLeiste />

    <!-- Zentrale Vollansicht: per Doppelklick/Detail-Pane geoeffnet, gerendert
         ueber die Vollansicht-Faehigkeit des aktiven Plugins (z.B. Bild-Lightbox). -->
    {#if vorschauZustand.knoten}
      {@const vf = vollansichtFuer(vorschauZustand.knoten)}
      {#if vf?.vollansicht}
        {@const Voll = vf.vollansicht}
        <Voll knoten={vorschauZustand.knoten} browser={haupt} schliessen={schliesseVollansicht} />
      {/if}
    {/if}
  </div>

  {#if zustand.uploads.length > 0}
    <UploadKarte />
  {/if}

  {#if zustand.vorgaengeOffen}
    <Vorgaenge />
  {/if}

  {#if neuerOrdnerOffen}
    <Modal titel="Neuer Ordner" schliessen={() => (neuerOrdnerOffen = false)}>
      <input
        class="feld"
        type="text"
        placeholder="Ordnername"
        bind:value={ordnerName}
        use:fokus
        onkeydown={(e) => e.key === "Enter" && ordnerAnlegenBestaetigen()}
      />
      <div class="modal-knoepfe">
        <button class="knopf still" onclick={() => (neuerOrdnerOffen = false)}>Abbrechen</button>
        <button class="knopf primaer" onclick={ordnerAnlegenBestaetigen}>Anlegen</button>
      </div>
    </Modal>
  {/if}

  {#if teilenKnoten}
    <Teilen knoten={teilenKnoten} schliessen={() => (teilenKnoten = null)} />
  {/if}

  {#if endgueltigKnoten}
    <Modal titel="Endgültig löschen" schliessen={() => (endgueltigKnoten = null)}>
      <p style="margin: 0; color: var(--text-2);">
        "{endgueltigKnoten.name}" wird endgültig gelöscht. Das lässt sich nicht rückgängig machen.
      </p>
      <div class="modal-knoepfe">
        <button class="knopf still" onclick={() => (endgueltigKnoten = null)}>Abbrechen</button>
        <button
          class="knopf primaer"
          onclick={() => {
            if (endgueltigKnoten) haupt.endgueltigLoeschen([endgueltigKnoten.id]);
            endgueltigKnoten = null;
          }}
        >
          <i class="fa-solid fa-trash"></i> Endgültig löschen
        </button>
      </div>
    </Modal>
  {/if}

  {#if papierkorbLeerenOffen}
    <Modal titel="Papierkorb leeren" schliessen={() => (papierkorbLeerenOffen = false)}>
      <p style="margin: 0; color: var(--text-2);">
        Alle Objekte im Papierkorb werden endgültig gelöscht. Das lässt sich nicht rückgängig
        machen.
      </p>
      <div class="modal-knoepfe">
        <button class="knopf still" onclick={() => (papierkorbLeerenOffen = false)}>Abbrechen</button>
        <button
          class="knopf primaer"
          onclick={() => {
            leerePapierkorb();
            papierkorbLeerenOffen = false;
          }}
        >
          <i class="fa-solid fa-trash-can"></i> Endgültig leeren
        </button>
      </div>
    </Modal>
  {/if}
{/if}

<style>
  .start-laden {
    height: 100vh;
    display: grid;
    place-items: center;
    font-size: 2.4rem;
    color: var(--akzent);
  }
  .modal-knoepfe {
    display: flex;
    justify-content: flex-end;
    gap: var(--a2);
  }
  .plugin-fehler {
    margin: var(--a5) auto;
    max-width: 560px;
    text-align: center;
    color: var(--text-2);
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--a3);
  }
  .plugin-fehler i {
    font-size: 2.2rem;
    color: var(--warn);
  }
  .plugin-fehler h3 {
    margin: 0;
    color: var(--text);
  }
  .plugin-fehler pre {
    max-width: 100%;
    overflow: auto;
    text-align: left;
    background: var(--flaeche-2);
    border: 1px solid var(--rand);
    border-radius: var(--r2);
    padding: var(--a3);
    font-size: 0.8rem;
    color: var(--gefahr);
    white-space: pre-wrap;
  }
  .pf-knoepfe {
    display: flex;
    gap: var(--a2);
  }
  .global-drop {
    position: fixed;
    inset: 0;
    z-index: 200;
    background: color-mix(in srgb, var(--akzent) 14%, transparent);
    backdrop-filter: blur(1px);
    display: grid;
    place-items: center;
    pointer-events: none;
    padding: var(--a4);
  }
  .global-drop-karte {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--a2);
    padding: var(--a5) var(--a6);
    border: 2px dashed var(--akzent);
    border-radius: var(--r3);
    background: var(--flaeche);
    color: var(--text);
    box-shadow: 0 10px 40px rgba(0, 0, 0, 0.18);
  }
  .global-drop-karte i {
    font-size: 2.6rem;
    color: var(--akzent);
  }
  .global-drop-karte span {
    color: var(--text-2);
    font-size: 0.9rem;
  }
</style>

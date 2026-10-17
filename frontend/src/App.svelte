<script lang="ts">
  import { onMount } from "svelte";
  import { auth, ladeStatus, abmelden } from "./lib/auth.svelte";
  import { thema, themaUmschalten } from "./lib/thema.svelte";
  import {
    zustand,
    haupt,
    leerePapierkorb,
    endgueltigLoeschen,
    ladeVersion,
    starteLiveAbgleich,
    stoppeLiveAbgleich,
    vorgaengeUmschalten,
    aktiveFlaeche,
    ablegen,
    hatDateien,
  } from "./lib/zustand.svelte";
  import type { Browser } from "./lib/browser.svelte";
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
  import Meldung from "./lib/Meldung.svelte";
  import Medien from "./lib/medien/Medien.svelte";
  import Vollansicht from "./lib/medien/Vollansicht.svelte";
  import { knotenOeffnen } from "./lib/medien/oeffnen";
  import { aktuelleSpur } from "./lib/player.svelte";
  import { ansicht, waehleAnsicht, medienEinstellung, MEDIEN_BEREICHE } from "./lib/ansicht.svelte";
  import type { Knoten } from "./lib/types";

  let verwaltungOffen = $state(false);
  let teilenKnoten = $state<Knoten | null>(null);
  let endgueltig = $state<{ ziel: Browser; knoten: Knoten[] } | null>(null);
  let nutzerMenuOffen = $state(false);
  let neuerOrdnerOffen = $state(false);
  let papierkorbLeerenOffen = $state(false);
  let ordnerName = $state("");
  let initialGeladen = $state(false);
  // Das Suchfeld gehört dem Kopf; gesucht wird erst mit Enter.
  let suchtext = $state("");

  onMount(ladeStatus);

  $effect(() => {
    if (auth.angemeldet && !initialGeladen) {
      initialGeladen = true;
      haupt.zeigeDateien();
      ladeVersion();
      starteLiveAbgleich();
    }
    if (!auth.angemeldet) {
      initialGeladen = false;
      stoppeLiveAbgleich();
    }
  });

  // Das Feld zeigt den Begriff der laufenden Suche und leert sich beim Verlassen.
  $effect(() => {
    suchtext = haupt.suchbegriff;
  });

  const istMedien = $derived(ansicht.aktiv === "medien");
  // Die Medienansicht gibt es nur dort, wo Medien liegen; sonst zurück zu den Dateien.
  $effect(() => {
    if (istMedien && !MEDIEN_BEREICHE.includes(haupt.bereich)) waehleAnsicht("dateien");
  });

  const istSplit = $derived(zustand.split && haupt.bereich === "dateien" && !istMedien);
  const mitDetail = $derived(!istMedien && haupt.detail !== null && haupt.auswahl.anzahl <= 1 && !istSplit);
  const avatarText = $derived((auth.benutzer?.name ?? "?").slice(0, 1).toUpperCase());
  const laufendeVorgaenge = $derived(zustand.vorgaenge.filter((v) => v.status === "laeuft").length);

  function suchen(e: Event) {
    e.preventDefault();
    haupt.starteSuche(suchtext);
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

  // --- Ablegen aus dem Dateisystem: überall im Fenster, Ziel ist die aktive
  // Fläche (Einzelansicht oder die zuletzt benutzte Pane). Liste und Panes
  // nehmen ihre Ablage selbst an; was hier ankommt, kam daneben an. ---
  let zieheDatei = $state(false);
  let ziehZaehler = 0; // dragenter/leave-Zähler gegen Flackern beim Überfahren von Kindelementen
  const ablageZiel = $derived(aktiveFlaeche());

  function aufDragEnter(e: DragEvent) {
    if (!auth.angemeldet || verwaltungOffen || !hatDateien(e)) return;
    e.preventDefault();
    ziehZaehler++;
    zieheDatei = true;
  }
  function aufDragOver(e: DragEvent) {
    if (!auth.angemeldet || verwaltungOffen || !hatDateien(e)) return;
    e.preventDefault();
    if (e.dataTransfer) e.dataTransfer.dropEffect = ablageZiel.istSchreibbar ? "copy" : "none";
  }
  function aufDragLeave(e: DragEvent) {
    if (!hatDateien(e)) return;
    ziehZaehler--;
    if (ziehZaehler <= 0) {
      ziehZaehler = 0;
      zieheDatei = false;
    }
  }
  function aufDrop(e: DragEvent) {
    ziehZaehler = 0;
    zieheDatei = false;
    if (!auth.angemeldet || verwaltungOffen || !hatDateien(e)) return;
    e.preventDefault();
    ablegen(e, ablageZiel);
  }
  // Ende eines Ziehens, das innerhalb einer Liste abgelegt wurde (dort endet das Ereignis).
  function aufDragEnd() {
    ziehZaehler = 0;
    zieheDatei = false;
  }
</script>

<svelte:window
  ondragenter={aufDragEnter}
  ondragover={aufDragOver}
  ondragleave={aufDragLeave}
  ondrop={aufDrop}
  ondragend={aufDragEnd}
  ondropcapture={aufDragEnd}
/>

{#if !auth.geladen}
  <div class="start-laden"><i class="fa-solid fa-cloud fa-beat-fade"></i></div>
{:else if !auth.angemeldet}
  <Login />
{:else if verwaltungOffen}
  <Einstellungen schliessen={() => (verwaltungOffen = false)} />
{:else}
  {#if zieheDatei}
    <div class="global-drop" class:gesperrt={!ablageZiel.istSchreibbar} role="presentation">
      <div class="global-drop-karte">
        {#if ablageZiel.istSchreibbar}
          <i class="fa-solid fa-cloud-arrow-up"></i>
          <strong>Dateien und Ordner hier ablegen</strong>
          <span>Sie landen in "{ablageZiel.zielName}" - Ordner mit ihrer Struktur.</span>
        {:else}
          <i class="fa-solid fa-ban"></i>
          <strong>Hier kann nichts abgelegt werden</strong>
          <span>Zum Hochladen einen Ordner in "Meine Dateien" öffnen.</span>
        {/if}
      </div>
    </div>
  {/if}
  <div class="app" class:mit-detail={mitDetail} class:nav-aus={zustand.navAus} class:mit-player={!!aktuelleSpur()}>
    <header class="kopf">
      <div class="marke"><Logo size={22} /> Kellerwolke</div>
      <form class="kopf-suche" onsubmit={suchen}>
        <i class="fa-solid fa-magnifying-glass"></i>
        <input type="text" enterkeyhint="search" placeholder="In allen Dateien suchen ..." bind:value={suchtext} />
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
              <button role="menuitem" onclick={() => { nutzerMenuOffen = false; verwaltungOffen = true; }}>
                <i class="fa-solid fa-gear"></i> {auth.benutzer?.rolle === "admin" ? "Verwaltung" : "Zugänge"}
              </button>
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
      {#if !istMedien}
        <Werkzeugleiste
          onNeuerOrdner={() => (neuerOrdnerOffen = true)}
          onPapierkorbLeeren={() => (papierkorbLeerenOffen = true)}
        />
        {#if istSplit}
          <Splitscreen
            onTeilen={(k) => (teilenKnoten = k)}
            onEndgueltig={(knoten) => (endgueltig = { ziel: aktiveFlaeche(), knoten })}
          />
        {:else}
          <Breadcrumb browser={haupt} />
          <Meldung browser={haupt} />
          <Dateiliste
            browser={haupt}
            onTeilen={(k) => (teilenKnoten = k)}
            onEndgueltig={(knoten) => (endgueltig = { ziel: haupt, knoten })}
          />
        {/if}
      {:else}
        {#if medienEinstellung.quelle === "alle"}
          <nav class="breadcrumb"><i class="fa-solid fa-layer-group"></i> <span class="aktuell">Alle Medien</span></nav>
        {:else}
          <Breadcrumb browser={haupt} />
        {/if}
        <Meldung browser={haupt} />
        <Medien browser={haupt} />
      {/if}
    </section>

    {#if mitDetail && haupt.detail}
      <DetailPane
        browser={haupt}
        k={haupt.detail}
        onTeilen={(k) => (teilenKnoten = k)}
        onOeffnen={(k) => knotenOeffnen(haupt, k)}
      />
    {/if}

    <PlayerLeiste />

    <!-- Die eine Vollansicht für Bilder und Videos, von überall geöffnet. -->
    <Vollansicht />
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
    <Teilen
      knoten={teilenKnoten}
      schliessen={() => {
        teilenKnoten = null;
        // Freigaben stehen nicht im Journal: das Kennzeichen sofort nachziehen.
        aktiveFlaeche().aktualisiere();
      }}
    />
  {/if}

  {#if endgueltig}
    {@const n = endgueltig.knoten.length}
    <Modal titel="Endgültig löschen" schliessen={() => (endgueltig = null)}>
      <p style="margin: 0; color: var(--text-2);">
        {n === 1 ? `"${endgueltig.knoten[0].name}" wird` : `${n} Objekte werden`} endgültig gelöscht. Das lässt sich
        nicht rückgängig machen.
      </p>
      <div class="modal-knoepfe">
        <button class="knopf still" onclick={() => (endgueltig = null)}>Abbrechen</button>
        <button
          class="knopf primaer"
          onclick={() => {
            if (endgueltig) endgueltigLoeschen(endgueltig.ziel, endgueltig.knoten.map((k) => k.id));
            endgueltig = null;
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
  .global-drop.gesperrt .global-drop-karte {
    border-color: var(--warn);
  }
  .global-drop.gesperrt .global-drop-karte i {
    color: var(--warn);
  }
</style>

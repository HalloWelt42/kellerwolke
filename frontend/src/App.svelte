<script lang="ts">
  import { onMount } from "svelte";
  import { auth, ladeStatus, abmelden } from "./lib/auth.svelte";
  import { thema, themaUmschalten } from "./lib/thema.svelte";
  import {
    zustand,
    starteSuche,
    zeigeDateien,
    ordnerAnlegen,
    leerePapierkorb,
    endgueltigLoeschen,
    ladeVersion,
    starteLiveAbgleich,
    stoppeLiveAbgleich,
  } from "./lib/zustand.svelte";
  import { auswahl } from "./lib/auswahl.svelte";
  import Login from "./lib/Login.svelte";
  import Navigation from "./lib/Navigation.svelte";
  import Werkzeugleiste from "./lib/Werkzeugleiste.svelte";
  import Breadcrumb from "./lib/Breadcrumb.svelte";
  import Dateiliste from "./lib/Dateiliste.svelte";
  import Splitscreen from "./lib/Splitscreen.svelte";
  import DetailPane from "./lib/DetailPane.svelte";
  import Einstellungen from "./lib/Einstellungen.svelte";
  import Teilen from "./lib/Teilen.svelte";
  import Modal from "./lib/Modal.svelte";
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
      zeigeDateien();
      ladeVersion();
      starteLiveAbgleich();
    }
    if (!auth.angemeldet) {
      initialGeladen = false;
      stoppeLiveAbgleich();
    }
  });

  const istSplit = $derived(zustand.ansicht === "split" && zustand.bereich === "dateien");
  const mitDetail = $derived(zustand.detail !== null && auswahl.anzahl <= 1 && !istSplit);
  const avatarText = $derived((auth.benutzer?.name ?? "?").slice(0, 1).toUpperCase());

  function suchen(e: Event) {
    e.preventDefault();
    starteSuche();
  }

  function ordnerAnlegenBestaetigen() {
    const name = ordnerName.trim();
    if (!name) return;
    ordnerAnlegen(name);
    ordnerName = "";
    neuerOrdnerOffen = false;
  }

  function fokus(el: HTMLInputElement) {
    el.focus();
  }
</script>

{#if !auth.geladen}
  <div class="start-laden"><i class="fa-solid fa-cloud fa-beat-fade"></i></div>
{:else if !auth.angemeldet}
  <Login />
{:else if verwaltungOffen}
  <Einstellungen schliessen={() => (verwaltungOffen = false)} />
{:else}
  <div class="app" class:mit-detail={mitDetail} class:nav-aus={zustand.navAus}>
    <header class="kopf">
      <div class="marke"><i class="fa-solid fa-cloud"></i> Kellerwolke</div>
      <form class="kopf-suche" onsubmit={suchen}>
        <i class="fa-solid fa-magnifying-glass"></i>
        <input
          type="text"
          placeholder="In allen Dateien suchen ..."
          bind:value={zustand.suchbegriff}
        />
        {#if zustand.bereich === "suche"}
          <button
            type="button"
            class="icon-knopf"
            title="Suche schließen"
            aria-label="Suche schließen"
            onclick={() => {
              zustand.suchbegriff = "";
              zeigeDateien();
            }}
          >
            <i class="fa-solid fa-xmark"></i>
          </button>
        {/if}
      </form>
      <div class="kopf-rechts">
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
      <Werkzeugleiste
        onNeuerOrdner={() => (neuerOrdnerOffen = true)}
        onPapierkorbLeeren={() => (papierkorbLeerenOffen = true)}
      />
      {#if istSplit}
        <Splitscreen />
      {:else}
        <Breadcrumb />
        {#if zustand.fehler}
          <div class="fehlerstreifen">{zustand.fehler}</div>
        {/if}
        <Dateiliste
          onTeilen={(k) => (teilenKnoten = k)}
          onEndgueltig={(k) => (endgueltigKnoten = k)}
        />
      {/if}
    </section>

    {#if mitDetail && zustand.detail}
      <DetailPane k={zustand.detail} onTeilen={(k) => (teilenKnoten = k)} />
    {/if}
  </div>

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
            if (endgueltigKnoten) endgueltigLoeschen([endgueltigKnoten.id]);
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
</style>

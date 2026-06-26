<script lang="ts">
  import * as api from "./api";
  import type { Benutzer } from "./types";
  import Modal from "./Modal.svelte";

  interface Props {
    schliessen: () => void;
  }
  let { schliessen }: Props = $props();

  let benutzer = $state<Benutzer[]>([]);
  let fehler = $state("");
  let laden = $state(true);

  let neuName = $state("");
  let neuPasswort = $state("");
  let neuRolle = $state("mitglied");

  let qBesitzer = $state("");
  let qName = $state("");
  let qPfad = $state("");
  let qMeldung = $state("");

  async function ladeKonten() {
    laden = true;
    fehler = "";
    try {
      benutzer = await api.listeBenutzer();
    } catch (f) {
      fehler = (f as Error).message;
    } finally {
      laden = false;
    }
  }
  ladeKonten();

  async function kontoAnlegen(e: Event) {
    e.preventDefault();
    fehler = "";
    try {
      await api.benutzerAnlegen(neuName.trim(), neuPasswort, neuRolle);
      neuName = "";
      neuPasswort = "";
      neuRolle = "mitglied";
      await ladeKonten();
    } catch (f) {
      fehler = (f as Error).message;
    }
  }

  async function aktivUmschalten(b: Benutzer) {
    try {
      await api.benutzerAktualisieren(b.id, { aktiv: !b.aktiv });
      await ladeKonten();
    } catch (f) {
      fehler = (f as Error).message;
    }
  }

  async function rolleSetzen(b: Benutzer, rolle: string) {
    try {
      await api.benutzerAktualisieren(b.id, { rolle });
      await ladeKonten();
    } catch (f) {
      fehler = (f as Error).message;
    }
  }

  async function quelleEinhaengen(e: Event) {
    e.preventDefault();
    qMeldung = "";
    try {
      await api.externeQuelleAnlegen(qBesitzer, qName.trim(), qPfad.trim());
      qMeldung = `Quelle "${qName}" eingehängt.`;
      qName = "";
      qPfad = "";
    } catch (f) {
      qMeldung = (f as Error).message;
    }
  }
</script>

<Modal titel="Verwaltung" {schliessen} breit>
  {#if fehler}<div class="fehler">{fehler}</div>{/if}

  <section>
    <h3>Konten</h3>
    {#if laden}
      <p class="leiser">Lädt ...</p>
    {:else}
      <ul class="konten">
        {#each benutzer as b (b.id)}
          <li>
            <span class="avatar">{b.name.slice(0, 1).toUpperCase()}</span>
            <span class="kname">{b.name}</span>
            <select
              class="feld schmal"
              value={b.rolle}
              onchange={(e) => rolleSetzen(b, (e.target as HTMLSelectElement).value)}
            >
              <option value="mitglied">Mitglied</option>
              <option value="admin">Admin</option>
            </select>
            <button
              class="status"
              class:gesperrt={!b.aktiv}
              onclick={() => aktivUmschalten(b)}
            >
              {b.aktiv ? "aktiv" : "gesperrt"}
            </button>
          </li>
        {/each}
      </ul>
    {/if}
    <form class="reihe" onsubmit={kontoAnlegen}>
      <input class="feld" type="text" placeholder="Name" bind:value={neuName} />
      <input class="feld" type="password" placeholder="Passwort" bind:value={neuPasswort} />
      <select class="feld schmal" bind:value={neuRolle}>
        <option value="mitglied">Mitglied</option>
        <option value="admin">Admin</option>
      </select>
      <button class="knopf primaer" type="submit" disabled={!neuName.trim() || !neuPasswort}>
        <i class="fa-solid fa-user-plus"></i> Anlegen
      </button>
    </form>
  </section>

  <section>
    <h3>Externe Quelle einhängen</h3>
    <p class="leiser">
      Bindet einen bestehenden Ordner vom Server schreibgeschützt ein, etwa ein angeschlossenes
      Laufwerk. Die Dateien bleiben am Ursprungsort (im Betrieb z.B. /extern).
    </p>
    <form class="spalte" onsubmit={quelleEinhaengen}>
      <select class="feld" bind:value={qBesitzer}>
        <option value="" disabled>Konto wählen ...</option>
        {#each benutzer as b (b.id)}<option value={b.id}>{b.name}</option>{/each}
      </select>
      <input class="feld" type="text" placeholder="Anzeigename (z.B. Archiv)" bind:value={qName} />
      <input class="feld" type="text" placeholder="Pfad auf dem Server (z.B. /extern/Fotos)" bind:value={qPfad} />
      <button class="knopf primaer" type="submit" disabled={!qBesitzer || !qName.trim() || !qPfad.trim()}>
        <i class="fa-solid fa-folder-tree"></i> Einhängen
      </button>
    </form>
    {#if qMeldung}<div class="meldung">{qMeldung}</div>{/if}
  </section>
</Modal>

<style>
  section {
    border-top: 1px solid var(--rand);
    padding-top: var(--a4);
  }
  section:first-of-type {
    border-top: none;
    padding-top: 0;
  }
  h3 {
    margin: 0 0 var(--a3);
    font-size: 0.74rem;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--text-3);
  }
  .leiser {
    color: var(--text-2);
    font-size: 0.85rem;
    margin: 0 0 var(--a3);
  }
  .konten {
    list-style: none;
    margin: 0 0 var(--a3);
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: var(--a2);
  }
  .konten li {
    display: flex;
    align-items: center;
    gap: var(--a3);
  }
  .kname {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .status {
    border: 1px solid var(--gut);
    background: var(--gut-weich);
    color: var(--gut);
    border-radius: var(--r2);
    padding: 0 var(--a3);
    height: 38px;
    min-width: 6rem;
    cursor: pointer;
    font: inherit;
  }
  .status.gesperrt {
    border-color: var(--gefahr);
    background: var(--gefahr-weich);
    color: var(--gefahr);
  }
  .reihe {
    display: flex;
    gap: var(--a2);
    flex-wrap: wrap;
  }
  .reihe input {
    flex: 1;
    min-width: 8rem;
  }
  .schmal {
    width: auto;
    min-width: 8rem;
  }
  .spalte {
    display: flex;
    flex-direction: column;
    gap: var(--a3);
  }
</style>

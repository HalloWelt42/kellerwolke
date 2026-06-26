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
    <h3><i class="fa-solid fa-users"></i> Konten</h3>
    {#if laden}
      <p class="gedaempft">Lädt ...</p>
    {:else}
      <ul class="konten">
        {#each benutzer as b (b.id)}
          <li>
            <span class="kname">{b.name}</span>
            <select value={b.rolle} onchange={(e) => rolleSetzen(b, (e.target as HTMLSelectElement).value)}>
              <option value="mitglied">Mitglied</option>
              <option value="admin">Admin</option>
            </select>
            <button class="still status" class:gesperrt={!b.aktiv} onclick={() => aktivUmschalten(b)}>
              {b.aktiv ? "aktiv" : "gesperrt"}
            </button>
          </li>
        {/each}
      </ul>
    {/if}
    <form class="zeile" onsubmit={kontoAnlegen}>
      <input type="text" placeholder="Name" bind:value={neuName} />
      <input type="password" placeholder="Passwort" bind:value={neuPasswort} />
      <select bind:value={neuRolle}>
        <option value="mitglied">Mitglied</option>
        <option value="admin">Admin</option>
      </select>
      <button class="primaer" type="submit" disabled={!neuName.trim() || !neuPasswort}>Anlegen</button>
    </form>
  </section>

  <section>
    <h3><i class="fa-solid fa-folder-tree"></i> Externe Quelle einhängen</h3>
    <p class="gedaempft">
      Hängt einen bestehenden Verzeichnisbaum read-only in das Konto eines Nutzers ein. Der Pfad
      muss für den Server erreichbar sein (im Betrieb z.B. /extern).
    </p>
    <form class="spalte" onsubmit={quelleEinhaengen}>
      <select bind:value={qBesitzer}>
        <option value="" disabled>Konto wählen ...</option>
        {#each benutzer as b (b.id)}<option value={b.id}>{b.name}</option>{/each}
      </select>
      <input type="text" placeholder="Anzeigename (z.B. Archiv)" bind:value={qName} />
      <input type="text" placeholder="Pfad auf dem Server (z.B. /extern/Fotos)" bind:value={qPfad} />
      <button class="primaer" type="submit" disabled={!qBesitzer || !qName.trim() || !qPfad.trim()}>
        Einhängen
      </button>
    </form>
    {#if qMeldung}<div class="meldung">{qMeldung}</div>{/if}
  </section>
</Modal>

<style>
  section {
    border-top: 1px solid var(--rand);
    padding-top: 1rem;
  }
  section:first-of-type {
    border-top: none;
    padding-top: 0;
  }
  h3 {
    margin: 0 0 0.6rem;
    font-size: 1rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }
  h3 i {
    color: var(--akzent);
  }
  .gedaempft {
    color: var(--gedaempft);
    font-size: 0.85rem;
    margin: 0 0 0.7rem;
  }
  .konten {
    list-style: none;
    margin: 0 0 0.8rem;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
  }
  .konten li {
    display: flex;
    align-items: center;
    gap: 0.6rem;
  }
  .kname {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .status {
    color: var(--gut);
    min-width: 5rem;
  }
  .status.gesperrt {
    color: var(--gefahr);
  }
  select {
    font-family: inherit;
    font-size: 14px;
    color: var(--text);
    background: var(--bg);
    border: 1px solid var(--rand);
    border-radius: 8px;
    padding: 0.45rem 0.55rem;
  }
  .zeile {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
  }
  .zeile input {
    flex: 1;
    min-width: 8rem;
  }
  .spalte {
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
  }
  .fehler {
    color: var(--gefahr);
    font-size: 0.85rem;
  }
  .meldung {
    color: var(--gut);
    font-size: 0.85rem;
  }
</style>

<script lang="ts">
  import * as api from "./api";
  import type { Freigabe, Knoten, Konto } from "./types";
  import { auth } from "./auth.svelte";
  import Modal from "./Modal.svelte";

  interface Props {
    knoten: Knoten;
    schliessen: () => void;
  }
  let { knoten, schliessen }: Props = $props();

  let konten = $state<Konto[]>([]);
  let liste = $state<Freigabe[]>([]);
  let ziel = $state("");
  let fehler = $state("");

  // Eigenes Konto nicht zur Auswahl anbieten.
  const auswahlbar = $derived(konten.filter((k) => k.id !== auth.benutzer?.id));

  async function ladeAlles() {
    fehler = "";
    try {
      [konten, liste] = await Promise.all([api.konten(), api.freigaben(knoten.id)]);
    } catch (f) {
      fehler = (f as Error).message;
    }
  }
  ladeAlles();

  async function teilen(e: Event) {
    e.preventDefault();
    if (!ziel) return;
    fehler = "";
    try {
      await api.teilen(knoten.id, ziel, "lesen");
      ziel = "";
      liste = await api.freigaben(knoten.id);
    } catch (f) {
      fehler = (f as Error).message;
    }
  }

  async function entfernen(f: Freigabe) {
    try {
      await api.teilenEntfernen(knoten.id, f.ziel_benutzer_id);
      liste = await api.freigaben(knoten.id);
    } catch (e) {
      fehler = (e as Error).message;
    }
  }
</script>

<Modal titel={`"${knoten.name}" teilen`} {schliessen}>
  {#if fehler}<div class="fehler">{fehler}</div>{/if}
  <form class="teil-reihe" onsubmit={teilen}>
    <select class="feld" bind:value={ziel}>
      <option value="" disabled>Konto wählen ...</option>
      {#each auswahlbar as k (k.id)}<option value={k.id}>{k.name}</option>{/each}
    </select>
    <button class="knopf primaer" type="submit" disabled={!ziel}>
      <i class="fa-solid fa-share-nodes"></i> Teilen
    </button>
  </form>

  <div class="geteilt-mit">
    <h3>Geteilt mit</h3>
    {#if liste.length === 0}
      <p class="leer-hinweis">Noch mit niemandem geteilt.</p>
    {:else}
      <ul>
        {#each liste as f (f.ziel_benutzer_id)}
          <li>
            <span class="avatar">{f.ziel_name.slice(0, 1).toUpperCase()}</span>
            <span class="gname">{f.ziel_name}</span>
            <span class="recht">Lesen</span>
            <button class="icon-knopf gefahr" title="Freigabe entfernen" onclick={() => entfernen(f)}>
              <i class="fa-solid fa-xmark"></i>
            </button>
          </li>
        {/each}
      </ul>
    {/if}
  </div>
</Modal>

<style>
  .teil-reihe {
    display: flex;
    gap: var(--a2);
  }
  .teil-reihe .feld {
    flex: 1;
  }
  .geteilt-mit h3 {
    font-size: 0.74rem;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--text-3);
    margin: 0 0 var(--a2);
  }
  .geteilt-mit ul {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: var(--a2);
  }
  .geteilt-mit li {
    display: flex;
    align-items: center;
    gap: var(--a2);
  }
  .geteilt-mit .gname {
    flex: 1;
  }
  .geteilt-mit .recht {
    font-size: 0.72rem;
    color: var(--text-2);
    border: 1px solid var(--rand-stark);
    border-radius: var(--r1);
    padding: 0 var(--a2);
  }
  .leer-hinweis {
    color: var(--text-3);
    margin: 0;
    font-size: 0.88rem;
  }
</style>

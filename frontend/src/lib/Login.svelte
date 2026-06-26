<script lang="ts">
  import { anmelden } from "./auth.svelte";

  let kennung = $state("");
  let passwort = $state("");
  let fehler = $state("");
  let laeuft = $state(false);

  async function absenden(e: Event) {
    e.preventDefault();
    fehler = "";
    laeuft = true;
    try {
      await anmelden(kennung, passwort);
    } catch {
      fehler = "Anmeldung fehlgeschlagen";
    } finally {
      laeuft = false;
    }
  }
</script>

<div class="huelle">
  <form class="karte" onsubmit={absenden}>
    <div class="marke"><i class="fa-solid fa-cloud"></i> Kellerwolke</div>
    <p class="unter">Die eigene Wolke im Keller</p>
    <label>
      Name oder Kürzel
      <input type="text" bind:value={kennung} autocomplete="username" />
    </label>
    <label>
      Passwort
      <input type="password" bind:value={passwort} autocomplete="current-password" />
    </label>
    {#if fehler}<div class="fehler">{fehler}</div>{/if}
    <button class="primaer" type="submit" disabled={laeuft}>
      {laeuft ? "Anmelden ..." : "Anmelden"}
    </button>
  </form>
</div>

<style>
  .huelle {
    height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 1rem;
  }
  .karte {
    width: min(360px, 92vw);
    background: var(--panel);
    border: 1px solid var(--rand);
    border-radius: var(--radius);
    box-shadow: var(--schatten);
    padding: 1.6rem;
    display: flex;
    flex-direction: column;
    gap: 0.9rem;
  }
  .marke {
    font-size: 1.5rem;
    font-weight: 600;
    display: flex;
    align-items: center;
    gap: 0.6rem;
  }
  .marke i {
    color: var(--akzent);
  }
  .unter {
    margin: 0 0 0.4rem;
    color: var(--gedaempft);
    font-size: 0.9rem;
  }
  label {
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
    font-size: 0.85rem;
    color: var(--gedaempft);
  }
  .fehler {
    color: var(--gefahr);
    font-size: 0.85rem;
  }
</style>

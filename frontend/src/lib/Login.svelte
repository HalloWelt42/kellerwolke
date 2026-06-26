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

<div class="login-hg">
  <form class="login-karte" onsubmit={absenden}>
    <div class="marke"><i class="fa-solid fa-cloud"></i> Kellerwolke</div>
    <p class="unter">Die eigene Wolke im Keller</p>
    <label>
      Name oder Kürzel
      <input class="feld" type="text" bind:value={kennung} autocomplete="username" />
    </label>
    <label>
      Passwort
      <input class="feld" type="password" bind:value={passwort} autocomplete="current-password" />
    </label>
    {#if fehler}<div class="fehler">{fehler}</div>{/if}
    <button class="knopf primaer" type="submit" disabled={laeuft} style="justify-content: center;">
      {laeuft ? "Anmelden ..." : "Anmelden"}
    </button>
  </form>
</div>

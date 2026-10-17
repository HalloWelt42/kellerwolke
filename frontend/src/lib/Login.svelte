<script lang="ts">
  // Anmeldung mit Passwort oder Koppeln mit einem Code vom Rechner (Entwurf: mockups/geraete-mobil.html).
  import { anmelden, mitCodeKoppeln } from "./auth.svelte";
  import { CODE_LAENGE, codeAusLinkNehmen, codeNormal, geraeteArt, namensvorschlag } from "./kopplung";
  import Logo from "./Logo.svelte";

  const ausLink = codeAusLinkNehmen();

  let modus = $state<"passwort" | "code">(ausLink ? "code" : "passwort");
  let kennung = $state("");
  let passwort = $state("");
  let code = $state(ausLink);
  let geraetName = $state(namensvorschlag());
  let codeFokus = $state(false);
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

  async function koppeln(e: Event) {
    e.preventDefault();
    fehler = "";
    laeuft = true;
    try {
      await mitCodeKoppeln(code, geraetName.trim(), geraeteArt());
    } catch (f) {
      fehler = (f as Error).message;
    } finally {
      laeuft = false;
    }
  }

  function wechseln(ziel: "passwort" | "code") {
    modus = ziel;
    fehler = "";
  }
</script>

<div class="login-hg">
  {#if modus === "passwort"}
    <form class="login-karte" onsubmit={absenden}>
      <div class="marke"><Logo size={22} /> Kellerwolke</div>
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
      <div class="oder">oder</div>
      <button class="knopf zweit" type="button" onclick={() => wechseln("code")}>
        <i class="fa-solid fa-link"></i> Mit Code koppeln
      </button>
      <p class="hinweis">Den Code zeigt die Kellerwolke am Rechner unter Einstellungen, Geräte.</p>
    </form>
  {:else}
    <form class="login-karte" onsubmit={koppeln}>
      <div class="kopf-zeile">
        <button class="icon-knopf" type="button" title="Zurück zur Anmeldung" onclick={() => wechseln("passwort")}>
          <i class="fa-solid fa-chevron-left"></i>
        </button>
        <h1>Gerät koppeln</h1>
      </div>
      <p class="hinweis links">
        Tipp den Code vom Rechner ein. Danach bleibt dieses Gerät angemeldet, bis du es trennst; dein Passwort wird hier
        nicht gespeichert.
      </p>
      {#if fehler}<div class="fehler"><i class="fa-solid fa-circle-exclamation"></i> {fehler}</div>{/if}
      <label class="code-feld">
        <span class="kaestchen" aria-hidden="true">
          {#each Array.from({ length: CODE_LAENGE }) as _, i (i)}
            {#if i === CODE_LAENGE / 2}<span class="luecke"></span>{/if}
            <span class="k" class:aktiv={codeFokus && i === Math.min(code.length, CODE_LAENGE - 1)}>{code[i] ?? ""}</span>
          {/each}
        </span>
        <input
          type="text"
          aria-label="Kopplungscode"
          value={code}
          oninput={(e) => {
            code = codeNormal(e.currentTarget.value);
            e.currentTarget.value = code;
          }}
          onfocus={() => (codeFokus = true)}
          onblur={() => (codeFokus = false)}
          autocomplete="one-time-code"
          autocapitalize="characters"
          spellcheck="false"
        />
      </label>
      <label>
        Name des Geräts
        <input class="feld" type="text" maxlength="60" bind:value={geraetName} />
      </label>
      <button class="knopf primaer" type="submit" disabled={laeuft || code.length !== CODE_LAENGE || !geraetName.trim()}
              style="justify-content: center;">
        <i class="fa-solid fa-link"></i> {laeuft ? "Koppeln ..." : "Koppeln"}
      </button>
    </form>
  {/if}
</div>

<style>
  .oder {
    display: flex;
    align-items: center;
    gap: var(--a2);
    color: var(--text-3);
    font-size: 0.82rem;
  }
  .oder::before,
  .oder::after {
    content: "";
    flex: 1;
    height: 1px;
    background: var(--rand);
  }
  .zweit {
    justify-content: center;
    background: var(--akzent-weich);
    color: var(--akzent);
    border-color: transparent;
  }
  .hinweis {
    margin: 0;
    font-size: 0.85rem;
    color: var(--text-2);
    text-align: center;
  }
  .hinweis.links {
    text-align: left;
  }
  .kopf-zeile {
    display: flex;
    align-items: center;
    gap: var(--a2);
  }
  .kopf-zeile h1 {
    margin: 0;
    font-size: 1.3rem;
  }
  .fehler {
    display: flex;
    gap: var(--a2);
    align-items: baseline;
  }
  .code-feld {
    position: relative;
  }
  .kaestchen {
    display: flex;
    gap: 6px;
    justify-content: center;
  }
  .k {
    flex: 1 1 0;
    min-width: 0;
    max-width: 34px;
    height: 48px;
    border-radius: var(--r2);
    border: 1px solid var(--rand);
    background: var(--flaeche);
    display: flex;
    align-items: center;
    justify-content: center;
    font-family: ui-monospace, monospace;
    font-size: 1.4rem;
    font-weight: 600;
    color: var(--text);
  }
  .k.aktiv {
    border-color: var(--akzent);
    box-shadow: 0 0 0 3px var(--akzent-weich);
  }
  .luecke {
    flex: none;
    width: 8px;
  }
  /* Das echte Feld liegt unsichtbar über den Kästchen: Tippen, Einfügen und Autofill gehen wie gewohnt. */
  .code-feld input {
    position: absolute;
    inset: 0;
    width: 100%;
    opacity: 0;
    font-size: 16px;
    caret-color: transparent;
  }
</style>

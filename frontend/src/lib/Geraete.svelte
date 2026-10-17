<script lang="ts">
  // Gekoppelte Geräte: Code und QR-Code zum Koppeln, Liste mit "zuletzt gesehen", umbenennen, trennen.
  // Entwurf: mockups/geraete.html.
  import { onDestroy } from "svelte";
  import * as api from "./api";
  import { abmelden } from "./auth.svelte";
  import { datum } from "./format";
  import Modal from "./Modal.svelte";
  import QrCode from "./QrCode.svelte";
  import {
    ART_TEXT, codeAnzeige, geraetSymbol, koppelLink, langeNichtGesehen, restText, zuletztText,
  } from "./kopplung";
  import type { Geraet, Kopplung } from "./types";

  const ABFRAGE_ALLE_S = 2;

  let geraete = $state<Geraet[]>([]);
  let laedt = $state(true);
  let fehler = $state("");
  let kopplung = $state<Kopplung | null>(null);
  let code = $state("");
  let rest = $state(0);
  let neuId = $state<string | null>(null);
  let umbenennen = $state<{ id: string; name: string } | null>(null);
  let trennen = $state<Geraet | null>(null);
  let takt: ReturnType<typeof setInterval> | null = null;
  let tick = 0;

  async function laden() {
    try {
      geraete = await api.geraete();
    } catch (f) {
      fehler = (f as Error).message;
    } finally {
      laedt = false;
    }
  }
  laden();

  async function tun(arbeit: () => Promise<unknown>) {
    fehler = "";
    try {
      await arbeit();
      await laden();
    } catch (f) {
      fehler = (f as Error).message;
    }
  }

  function taktAus() {
    if (takt) clearInterval(takt);
    takt = null;
  }

  async function starten() {
    fehler = "";
    neuId = null;
    try {
      const k = await api.kopplungStarten();
      kopplung = k;
      code = k.code ?? "";
      rest = (new Date(k.ablauf).getTime() - Date.now()) / 1000;
      taktAus();
      tick = 0;
      takt = setInterval(schlag, 1000);
    } catch (f) {
      fehler = (f as Error).message;
    }
  }

  // Jede Sekunde die Restzeit, alle paar Sekunden fragen, ob ein Gerät den Code eingelöst hat.
  async function schlag() {
    if (!kopplung) return taktAus();
    rest = (new Date(kopplung.ablauf).getTime() - Date.now()) / 1000;
    if (rest <= 0) {
      kopplung = { ...kopplung, stand: "abgelaufen" };
      return taktAus();
    }
    if (++tick % ABFRAGE_ALLE_S) return;
    try {
      const k = await api.kopplungStand(kopplung.id);
      if (k.stand === "gekoppelt") {
        taktAus();
        neuId = k.geraet?.id ?? null;
        kopplung = null;
        await laden();
      }
    } catch {
      // nächster Schlag versucht es wieder
    }
  }

  function abbrechen() {
    const k = kopplung;
    taktAus();
    kopplung = null;
    if (k && k.stand === "wartet") api.kopplungAbbrechen(k.id).catch(() => {});
  }
  onDestroy(abbrechen);

  function speichern(e: Event) {
    e.preventDefault();
    if (!umbenennen) return;
    const u = umbenennen;
    tun(async () => {
      await api.geraetUmbenennen(u.id, u.name.trim());
      umbenennen = null;
    });
  }

  async function trennenBestaetigt(g: Geraet) {
    trennen = null;
    if (g.dieses) return abmelden(); // dieser Browser selbst: trennt sich und zeigt die Anmeldung
    await tun(() => api.geraetTrennen(g.id));
  }
</script>

<h1>Geräte</h1>
<p class="unter">
  Telefon und Tablet bleiben angemeldet, ohne dass dort dein Passwort liegt. Jedes Gerät bekommt beim Koppeln einen
  eigenen Schlüssel und darf damit alles, was dein Konto darf. Geht eines verloren, trennst du es hier; sein Schlüssel
  gilt sofort nicht mehr.
</p>

{#if fehler}<div class="fehlerstreifen">{fehler}</div>{/if}

{#if kopplung}
  <div class="koppel-box">
    <div class="kb-qr">
      {#if kopplung.stand === "wartet"}<QrCode text={koppelLink(code)} />{/if}
    </div>
    <div>
      <div class="kb-kopf"><i class="fa-solid fa-link"></i> Neues Gerät koppeln</div>
      {#if kopplung.stand === "wartet"}
        <div class="kb-code">{codeAnzeige(code)}</div>
        <div class="kb-gueltig">gilt noch {restText(rest)} Minuten und nur für ein Gerät</div>
        <ol class="kb-wege">
          <li>Web-App auf dem Home-Bildschirm: auf der Anmeldeseite <b>Mit Code koppeln</b> wählen und den Code eintippen.</li>
          <li>Browser auf dem Telefon: die Kamera auf den QR-Code halten, der Code ist dann schon eingetragen.</li>
        </ol>
        <div class="kb-fuss">
          <span class="kb-warten"><i class="fa-solid fa-circle-notch fa-spin"></i> Wartet auf das Gerät</span>
          <button class="knopf still" onclick={abbrechen}>Abbrechen</button>
        </div>
      {:else}
        <p class="kb-gueltig">Der Code ist abgelaufen, ohne dass ein Gerät ihn benutzt hat.</p>
        <div class="kb-fuss">
          <button class="knopf primaer" onclick={starten}><i class="fa-solid fa-rotate"></i> Neuen Code erzeugen</button>
          <button class="knopf still" onclick={abbrechen}>Schließen</button>
        </div>
      {/if}
    </div>
  </div>
{/if}

<div class="karte">
  <h2><i class="fa-solid fa-mobile-screen"></i> Gekoppelte Geräte</h2>
  <p class="karte-unter">Zuletzt gesehen heißt: die letzte Anfrage dieses Geräts an die Kellerwolke.</p>

  {#if laedt}
    <p class="karte-unter">Lädt ...</p>
  {:else if !geraete.length}
    <p class="karte-unter">Noch kein Gerät gekoppelt.</p>
  {/if}

  {#each geraete as g (g.id)}
    {@const alt = langeNichtGesehen(g)}
    <div class="zugang" class:neu={g.id === neuId} class:alt>
      <div class="so-icon"><i class="fa-solid {geraetSymbol(g)}"></i></div>
      <div class="so-haupt">
        {#if umbenennen?.id === g.id}
          <form class="umbenennen" onsubmit={speichern}>
            <!-- svelte-ignore a11y_autofocus -->
            <input class="feld" type="text" maxlength="60" bind:value={umbenennen.name} autofocus />
            <button class="knopf still" type="button" onclick={() => (umbenennen = null)}>Abbrechen</button>
            <button class="knopf primaer" type="submit" disabled={!umbenennen.name.trim()}>
              <i class="fa-solid fa-check"></i> Speichern
            </button>
          </form>
        {:else}
          <div class="so-kopf">
            <span class="so-name">{g.name}</span>
            {#if g.id === neuId}<span class="marke-neu">gerade gekoppelt</span>{/if}
            {#if g.dieses}<span class="marke-std">dieses Gerät</span>{/if}
            {#if alt}<span class="marke-ro">lange nicht gesehen</span>{/if}
            <span class="zg-zeit">{zuletztText(g)}</span>
          </div>
        {/if}
        <div class="zg-meta">
          {ART_TEXT[g.art]} · gekoppelt am {datum(g.gekoppelt_am)}{#if g.zuletzt_adresse} · aus {g.zuletzt_adresse}{/if}{#if alt} · Wird es nicht mehr benutzt, trenn es.{/if}
        </div>
      </div>
      {#if umbenennen?.id !== g.id}
        <div class="so-akt">
          <button class="icon-knopf" title="Umbenennen" onclick={() => (umbenennen = { id: g.id, name: g.name })}>
            <i class="fa-solid fa-pen"></i>
          </button>
          <button class="icon-knopf gefahr" title="Trennen (das Gerät ist sofort abgemeldet)" onclick={() => (trennen = g)}>
            <i class="fa-solid fa-link-slash"></i>
          </button>
        </div>
      {/if}
    </div>
  {/each}

  {#if !kopplung}
    <div class="formzeile">
      <button class="knopf primaer" onclick={starten}><i class="fa-solid fa-link"></i> Gerät koppeln</button>
    </div>
  {/if}
</div>

<p class="fussnote">
  Ein Code gilt zehn Minuten und nur einmal; mehrere falsche Versuche hintereinander bremsen die Kopplung kurz aus.
  Anmeldungen im Browser mit Passwort bleiben, wie sie sind, und erscheinen hier nicht.
</p>

{#if trennen}
  {@const g = trennen}
  <Modal titel="Gerät trennen" schliessen={() => (trennen = null)}>
    {#if g.dieses}
      <p><b>{g.name}</b> ist dieses Gerät. Trennen meldet dich hier ab; zum Wiederkommen koppelst du neu.</p>
    {:else}
      <p><b>{g.name}</b> trennen? Das Gerät ist sofort abgemeldet; zum Wiederkommen koppelst du es neu.</p>
    {/if}
    <div class="rb-fuss">
      <button class="knopf still" onclick={() => (trennen = null)}>Abbrechen</button>
      <button class="knopf gefahr" onclick={() => trennenBestaetigt(g)}><i class="fa-solid fa-link-slash"></i> Trennen</button>
    </div>
  </Modal>
{/if}

<style>
  .koppel-box {
    max-width: 880px;
    margin-bottom: var(--a4);
    padding: var(--a4);
    border-radius: var(--r3);
    border: 1px solid var(--akzent);
    background: var(--akzent-weich);
    display: grid;
    grid-template-columns: auto minmax(0, 1fr);
    gap: var(--a4);
    align-items: start;
  }
  .kb-qr {
    padding: 10px;
    background: #fff;
    border-radius: var(--r2);
    line-height: 0;
  }
  .kb-qr:empty {
    display: none;
  }
  .kb-kopf {
    display: flex;
    align-items: center;
    gap: var(--a2);
    font-weight: 600;
    margin-bottom: var(--a2);
  }
  .kb-kopf i {
    color: var(--akzent);
  }
  .kb-code {
    font-family: ui-monospace, monospace;
    font-size: 2rem;
    letter-spacing: 0.12em;
    font-weight: 600;
    user-select: all;
  }
  .kb-gueltig {
    font-size: 0.85rem;
    color: var(--text-2);
    margin: 2px 0 var(--a3);
  }
  .kb-wege {
    margin: 0 0 var(--a3);
    padding-left: 1.2em;
    color: var(--text-2);
    font-size: 0.92rem;
  }
  .kb-wege li + li {
    margin-top: 4px;
  }
  .kb-fuss {
    display: flex;
    align-items: center;
    gap: var(--a3);
    flex-wrap: wrap;
  }
  .kb-warten {
    color: var(--text-2);
    font-size: 0.9rem;
    display: inline-flex;
    gap: 8px;
    align-items: center;
  }
  .zugang.neu {
    outline: 2px solid var(--gut);
    outline-offset: -2px;
    border-radius: var(--r2);
  }
  .zugang.alt .so-name,
  .zugang.alt .zg-zeit {
    color: var(--text-3);
  }
  .marke-neu {
    font-size: 0.75rem;
    padding: 1px 8px;
    border-radius: 10px;
    background: var(--gut-weich);
    color: var(--gut);
  }
  .zg-meta {
    font-size: 0.85rem;
    color: var(--text-2);
    margin-top: 2px;
  }
  .umbenennen {
    display: flex;
    gap: var(--a2);
    align-items: center;
    flex-wrap: wrap;
  }
  .umbenennen .feld {
    max-width: 260px;
  }
  .fussnote {
    max-width: 880px;
    font-size: 0.85rem;
    color: var(--text-2);
    margin-top: var(--a3);
  }
  @media (max-width: 700px) {
    .koppel-box {
      grid-template-columns: minmax(0, 1fr);
    }
  }
</style>

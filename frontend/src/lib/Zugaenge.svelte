<script lang="ts">
  // Zugänge für eigene Apps: Schlüssel je App, Rechte je Ordner (gemeinsame Arbeitsordner für mehrere Apps),
  // Schlüssel nur einmal sichtbar, sperren, erneuern, entfernen. Entwurf: mockups/zugaenge.html.
  import * as api from "./api";
  import { datum } from "./format";
  import Modal from "./Modal.svelte";
  import { kopieren, markieren } from "./zwischenablage";
  import OrdnerWahl from "./OrdnerWahl.svelte";
  import type { AppRecht, AppZugang, Recht } from "./types";

  let zugaenge = $state<AppZugang[]>([]);
  let laedt = $state(true);
  let fehler = $state("");
  let neuApp = $state("");
  let neuerSchluessel = $state<{ app: string; schluessel: string } | null>(null);
  let kopiert = $state(false);
  let bearbeiten = $state<{ id: string; rechte: AppRecht[] } | null>(null);
  let ordnerWahlOffen = $state(false);
  let entfernen = $state<AppZugang | null>(null);
  let schluesselFeld = $state<HTMLElement>();

  const SYMBOL: Record<string, string> = {
    transkription: "fa-closed-captioning",
    stimmenausgabe: "fa-comment-dots",
    vertonung: "fa-film",
    tonbearbeitung: "fa-wave-square",
    assistent: "fa-robot",
  };
  const symbol = (app: string) => SYMBOL[app.toLowerCase()] ?? "fa-plug";

  function genutzt(z: AppZugang): string {
    if (!z.zuletzt_genutzt) return "noch nie genutzt";
    const s = (Date.now() - new Date(z.zuletzt_genutzt).getTime()) / 1000;
    if (s < 90) return "zuletzt genutzt gerade eben";
    if (s < 3600) return `zuletzt genutzt vor ${Math.round(s / 60)} Minuten`;
    return `zuletzt genutzt ${datum(z.zuletzt_genutzt)}`;
  }

  async function laden() {
    laedt = true;
    try {
      zugaenge = await api.zugaenge();
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

  function anlegen(e: Event) {
    e.preventDefault();
    const app = neuApp.trim();
    tun(async () => {
      const neu = await api.zugangAnlegen(app);
      neuerSchluessel = { app: neu.zugang.app, schluessel: neu.schluessel };
      kopiert = false;
      neuApp = "";
    });
  }

  function erneuern(z: AppZugang) {
    tun(async () => {
      const neu = await api.zugangErneuern(z.id);
      neuerSchluessel = { app: z.app, schluessel: neu.schluessel };
      kopiert = false;
    });
  }

  async function schluesselKopieren() {
    if (!neuerSchluessel) return;
    fehler = "";
    kopiert = await kopieren(neuerSchluessel.schluessel);
    if (!kopiert) {
      markieren(schluesselFeld);
      fehler = "Der Browser lässt hier nicht kopieren. Der Schlüssel ist markiert: mit Befehlstaste+C oder Strg+C kopieren.";
    }
  }

  function rechteSpeichern() {
    if (!bearbeiten) return;
    const b = bearbeiten;
    tun(async () => {
      await api.zugangRechte(b.id, b.rechte.map((r) => ({ knoten_id: r.knoten_id, recht: r.recht })));
      bearbeiten = null;
    });
  }

  function ordnerGewaehlt(o: { id: string; pfad: string }) {
    ordnerWahlOffen = false;
    if (!bearbeiten || bearbeiten.rechte.some((r) => r.knoten_id === o.id)) return;
    bearbeiten.rechte = [...bearbeiten.rechte, { knoten_id: o.id, pfad: o.pfad, recht: "lesen" as Recht }];
  }
</script>

<h1>Zugänge</h1>
<p class="unter">
  Eigene Apps greifen mit einem Schlüssel auf deine Dateien zu, ohne Browser und ohne dein Passwort. Jede App arbeitet
  in ihrem Ordner unter <span class="pfad-text">Apps</span> und nur in den Ordnern, die du ihr freigibst. Ordner, die
  mehrere Apps beschreiben dürfen, sind gemeinsame Arbeitsordner.
</p>

{#if fehler}<div class="fehlerstreifen">{fehler}</div>{/if}

{#if neuerSchluessel}
  <div class="schluessel-box">
    <div class="sb-kopf"><i class="fa-solid fa-key"></i> Schlüssel für <b>{neuerSchluessel.app}</b> ausgestellt</div>
    <div class="sb-zeile">
      <code class="sb-wert" bind:this={schluesselFeld}>{neuerSchluessel.schluessel}</code>
      <button class="knopf primaer" onclick={schluesselKopieren}>
        <i class="fa-solid {kopiert ? 'fa-check' : 'fa-copy'}"></i> {kopiert ? "Kopiert" : "Kopieren"}
      </button>
    </div>
    <p class="sb-hinweis">
      Nur jetzt sichtbar. Trag ihn in den Einstellungen der App ein; danach zeigt die Kellerwolke ihn nie wieder. Geht er
      verloren, stellst du einen neuen aus.
      <button class="knopf still klein" onclick={() => (neuerSchluessel = null)}>Ausblenden</button>
    </p>
  </div>
{/if}

<div class="karte">
  <h2><i class="fa-solid fa-plug"></i> Apps</h2>
  <p class="karte-unter">Ein Schlüssel je App. Rechte gelten für den Ordner und alles darunter; schreiben schließt lesen ein.</p>

  {#if laedt}
    <p class="karte-unter">Lädt ...</p>
  {:else if !zugaenge.length}
    <p class="karte-unter">Noch keine Zugänge. Stell unten einen Schlüssel für deine erste App aus.</p>
  {/if}

  {#each zugaenge as z (z.id)}
    <div class="zugang" class:gesperrt={!z.aktiv} class:offen={bearbeiten?.id === z.id}>
      <div class="so-icon"><i class="fa-solid {symbol(z.app)}"></i></div>
      <div class="so-haupt">
        <div class="so-kopf">
          <span class="so-name">{z.app}</span>
          {#if z.aktiv}<span class="marke-std">aktiv</span>{:else}<span class="marke-ro">gesperrt</span>{/if}
          <span class="zg-zeit">{genutzt(z)}</span>
        </div>
        {#if bearbeiten?.id === z.id}
          <div class="rechte-bearbeiten">
            {#each bearbeiten.rechte as r, i (r.knoten_id)}
              <div class="rb-zeile">
                <span class="pfad-text"><i class="fa-solid fa-folder"></i> {r.pfad}</span>
                <select class="feld" bind:value={bearbeiten.rechte[i].recht}>
                  <option value="schreiben">schreiben</option>
                  <option value="lesen">lesen</option>
                </select>
                <button class="icon-knopf gefahr" title="Recht entfernen"
                        onclick={() => bearbeiten && (bearbeiten.rechte = bearbeiten.rechte.filter((x) => x.knoten_id !== r.knoten_id))}>
                  <i class="fa-solid fa-trash"></i>
                </button>
              </div>
            {/each}
            <div class="rb-zeile neu">
              <button class="knopf still" onclick={() => (ordnerWahlOffen = true)}><i class="fa-solid fa-folder-plus"></i> Ordner hinzufügen</button>
              <span class="rb-hinweis">Ordner aus deinen Dateien wählen</span>
            </div>
            <div class="rb-fuss">
              <button class="knopf still" onclick={() => (bearbeiten = null)}>Abbrechen</button>
              <button class="knopf primaer" onclick={rechteSpeichern}><i class="fa-solid fa-check"></i> Rechte speichern</button>
            </div>
          </div>
        {:else}
          <div class="rechte">
            {#each z.rechte as r (r.knoten_id)}
              <span class="recht {r.recht}" title={r.recht === "schreiben" ? "lesen und schreiben" : "nur lesen"}>
                <i class="fa-solid {r.recht === 'schreiben' ? 'fa-pen' : 'fa-eye'}"></i> {r.pfad}
              </span>
            {:else}
              <span class="zg-zeit">keine Rechte: die App sieht nichts</span>
            {/each}
          </div>
        {/if}
      </div>
      {#if bearbeiten?.id !== z.id}
        <div class="so-akt">
          {#if z.aktiv}
            <button class="icon-knopf" title="Rechte bearbeiten"
                    onclick={() => (bearbeiten = { id: z.id, rechte: z.rechte.map((r) => ({ ...r })) })}>
              <i class="fa-solid fa-folder-tree"></i>
            </button>
            <button class="icon-knopf" title="Neuen Schlüssel ausstellen (der alte gilt sofort nicht mehr)" onclick={() => erneuern(z)}>
              <i class="fa-solid fa-rotate"></i>
            </button>
            <button class="icon-knopf" title="Sperren" onclick={() => tun(() => api.zugangAktiv(z.id, false))}>
              <i class="fa-solid fa-lock"></i>
            </button>
          {:else}
            <button class="icon-knopf" title="Entsperren" onclick={() => tun(() => api.zugangAktiv(z.id, true))}>
              <i class="fa-solid fa-lock-open"></i>
            </button>
          {/if}
          <button class="icon-knopf gefahr" title="Zugang entfernen (die Dateien der App bleiben)" onclick={() => (entfernen = z)}>
            <i class="fa-solid fa-xmark"></i>
          </button>
        </div>
      {/if}
    </div>
  {/each}

  <form class="formzeile" onsubmit={anlegen}>
    <input class="feld" type="text" maxlength="60" placeholder="Name der App (zugleich ihr Ordner unter Apps)" bind:value={neuApp} />
    <button class="knopf primaer" type="submit" disabled={!neuApp.trim()}><i class="fa-solid fa-key"></i> Schlüssel ausstellen</button>
  </form>
</div>

{#if ordnerWahlOffen}
  <OrdnerWahl waehlen={ordnerGewaehlt} schliessen={() => (ordnerWahlOffen = false)} />
{/if}

{#if entfernen}
  {@const z = entfernen}
  <Modal titel="Zugang entfernen" schliessen={() => (entfernen = null)}>
    <p>Den Zugang für <b>{z.app}</b> entfernen? Die App kommt danach nicht mehr an deine Dateien. Ihre Dateien unter
      <span class="pfad-text">Apps/{z.app}</span> bleiben erhalten.</p>
    <div class="rb-fuss">
      <button class="knopf still" onclick={() => (entfernen = null)}>Abbrechen</button>
      <button class="knopf gefahr" onclick={() => { entfernen = null; tun(() => api.zugangLoeschen(z.id)); }}>
        <i class="fa-solid fa-xmark"></i> Entfernen
      </button>
    </div>
  </Modal>
{/if}

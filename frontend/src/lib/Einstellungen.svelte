<script lang="ts">
  import * as api from "./api";
  import Logo from "./Logo.svelte";
  import type { Benutzer, SpeicherStatus } from "./types";
  import { groesseText } from "./format";
  import { auth } from "./auth.svelte";

  interface Props {
    schliessen: () => void;
  }
  let { schliessen }: Props = $props();

  type Seite = "konten" | "extern" | "speicher";
  let seite = $state<Seite>("konten");
  let fehler = $state("");

  // --- Konten ---------------------------------------------------------------
  let benutzer = $state<Benutzer[]>([]);
  let kontenLaden = $state(true);
  let neuName = $state("");
  let neuPasswort = $state("");
  let neuRolle = $state("mitglied");

  async function ladeKonten() {
    kontenLaden = true;
    fehler = "";
    try {
      benutzer = await api.listeBenutzer();
    } catch (f) {
      fehler = (f as Error).message;
    } finally {
      kontenLaden = false;
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

  // --- Externe Quelle -------------------------------------------------------
  let qBesitzer = $state("");
  let qName = $state("");
  let qPfad = $state("");
  let qMeldung = $state("");

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

  // --- Speicherorte ---------------------------------------------------------
  let status = $state<SpeicherStatus | null>(null);
  const prozent = $derived(
    status && status.gesamt ? Math.min(100, Math.round((status.benutzt / status.gesamt) * 100)) : 0,
  );
  async function ladeStatus() {
    try {
      status = await api.speicherStatus();
    } catch {
      // optional
    }
  }
  ladeStatus();

  // Datenablage verschieben
  let zielPfad = $state("");
  let verschiebung = $state<import("./types").Verschiebung | null>(null);
  let verschiebeFehler = $state("");
  let pollTimer: ReturnType<typeof setInterval> | null = null;

  const moveProzent = $derived(
    verschiebung && verschiebung.gesamt > 0
      ? Math.round((verschiebung.kopiert / verschiebung.gesamt) * 100)
      : 0,
  );

  async function starteVerschieben() {
    const ziel = zielPfad.trim();
    if (!ziel) return;
    verschiebeFehler = "";
    try {
      verschiebung = await api.datenablageVerschieben(ziel);
      pollTimer = setInterval(async () => {
        try {
          verschiebung = await api.verschiebungStand();
          if (verschiebung.status === "fertig" || verschiebung.status === "fehler") {
            if (pollTimer) clearInterval(pollTimer);
            pollTimer = null;
            if (verschiebung.status === "fehler") verschiebeFehler = verschiebung.fehler ?? "Fehler";
            else zielPfad = "";
            await ladeStatus();
          }
        } catch {
          // weiter pollen
        }
      }, 1000);
    } catch (f) {
      verschiebeFehler = (f as Error).message;
    }
  }

  // Konsistenz / Reparatur (Vorschau, dann auf Wunsch aufraeumen)
  let pruefung = $state<import("./types").PoolPruefung | null>(null);
  let pruefeTief = $state(false);
  let pruefeLaeuft = $state(false);
  let pruefeFehler = $state("");
  let aufraeumMeldung = $state("");

  async function poolPruefen() {
    pruefeLaeuft = true;
    pruefeFehler = "";
    aufraeumMeldung = "";
    try {
      pruefung = await api.poolPruefung(pruefeTief);
    } catch (f) {
      pruefeFehler = (f as Error).message;
    } finally {
      pruefeLaeuft = false;
    }
  }

  async function poolAufraeumen() {
    pruefeLaeuft = true;
    pruefeFehler = "";
    try {
      const erg = await api.poolAufraeumen();
      // Erst neu prüfen (das setzt die Meldung zurück), dann die Erfolgsmeldung
      // setzen - sonst würde der Re-Scan sie sofort wieder löschen.
      await poolPruefen();
      await ladeStatus();
      aufraeumMeldung = `${erg.entfernt} verwaiste Blöcke entfernt, ${groesseText(erg.bytes)} frei.`;
    } catch (f) {
      pruefeFehler = (f as Error).message;
    } finally {
      pruefeLaeuft = false;
    }
  }
</script>

<div class="app">
  <header class="kopf">
    <div class="marke"><Logo size={22} /> Kellerwolke</div>
    <nav class="breadcrumb" style="padding: 0;">
      <i class="fa-solid fa-gear"></i> <span class="aktuell">Einstellungen</span>
    </nav>
    <div class="kopf-rechts">
      <button class="knopf still" onclick={schliessen}>
        <i class="fa-solid fa-arrow-left"></i> Zu den Dateien
      </button>
    </div>
  </header>

  <nav class="einst-nav">
    <div class="nav-titel">Einstellungen</div>
    <button class="einst-eintrag" class:aktiv={seite === "konten"} onclick={() => (seite = "konten")}>
      <i class="fa-solid fa-users"></i> Konten
    </button>
    <button
      class="einst-eintrag"
      class:aktiv={seite === "speicher"}
      onclick={() => (seite = "speicher")}
    >
      <i class="fa-solid fa-hard-drive"></i> Speicherorte
    </button>
    <button class="einst-eintrag" class:aktiv={seite === "extern"} onclick={() => (seite = "extern")}>
      <i class="fa-solid fa-folder-tree"></i> Externe Quellen
    </button>
  </nav>

  <section class="einst-inhalt">
    {#if fehler}<div class="fehlerstreifen">{fehler}</div>{/if}

    {#if seite === "konten"}
      <h1>Konten</h1>
      <p class="unter">Familienkonten anlegen, Rolle setzen und sperren.</p>
      <div class="karte">
        {#if kontenLaden}
          <p class="karte-unter">Lädt ...</p>
        {:else}
          <ul class="einst-konten">
            {#each benutzer as b (b.id)}
              <li>
                <span class="avatar">{b.name.slice(0, 1).toUpperCase()}</span>
                <span class="kname">{b.name}</span>
                <select
                  class="feld schmal"
                  value={b.rolle}
                  disabled={b.id === auth.benutzer?.id}
                  onchange={(e) => rolleSetzen(b, (e.target as HTMLSelectElement).value)}
                >
                  <option value="mitglied">Mitglied</option>
                  <option value="admin">Admin</option>
                </select>
                <button
                  class="einst-status"
                  class:gesperrt={!b.aktiv}
                  disabled={b.id === auth.benutzer?.id}
                  title={b.id === auth.benutzer?.id
                    ? "Das eigene Konto kann nicht gesperrt werden"
                    : undefined}
                  onclick={() => aktivUmschalten(b)}
                >
                  {b.aktiv ? "aktiv" : "gesperrt"}
                </button>
              </li>
            {/each}
          </ul>
          <form class="einst-reihe" onsubmit={kontoAnlegen}>
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
        {/if}
      </div>
    {:else if seite === "extern"}
      <h1>Externe Quellen</h1>
      <p class="unter">
        Bindet einen bestehenden Ordner vom Server schreibgeschützt in das Konto eines Nutzers ein.
        Die Dateien bleiben am Ursprungsort.
      </p>
      <div class="karte">
        <h2><i class="fa-solid fa-folder-tree"></i> Quelle einhängen</h2>
        <form class="einst-spalte" onsubmit={quelleEinhaengen}>
          <select class="feld" bind:value={qBesitzer}>
            <option value="" disabled>Konto wählen ...</option>
            {#each benutzer as b (b.id)}<option value={b.id}>{b.name}</option>{/each}
          </select>
          <input class="feld" type="text" placeholder="Anzeigename (z.B. Archiv)" bind:value={qName} />
          <input
            class="feld"
            type="text"
            placeholder="Pfad auf dem Server (z.B. /extern/Fotos)"
            bind:value={qPfad}
          />
          <button
            class="knopf primaer"
            type="submit"
            disabled={!qBesitzer || !qName.trim() || !qPfad.trim()}
          >
            <i class="fa-solid fa-folder-tree"></i> Einhängen
          </button>
        </form>
        {#if qMeldung}<div class="meldung">{qMeldung}</div>{/if}
      </div>
    {:else if seite === "speicher"}
      <h1>Speicherorte</h1>
      <p class="unter">
        Wo Kellerwolke die Dateien physisch ablegt. Die Datenablage ist vom Projekt getrennt und
        soll auf eine eigene/große Platte verschiebbar sein.
      </p>
      <div class="karte">
        <h2><i class="fa-solid fa-hard-drive"></i> Aktueller Speicherort</h2>
        {#if status}
          <div class="speicherort">
            <div class="so-icon"><i class="fa-solid fa-hard-drive"></i></div>
            <div class="so-haupt">
              <div class="so-kopf">
                <span class="so-name">Objekt-Pool</span>
                <span class="marke-std">Standard</span>
              </div>
              <div class="so-pfad">{status.ort ?? "-"}</div>
              <div class="so-bar">
                <div class="balken"><span style="width: {prozent}%"></span></div>
                <span class="text">
                  {groesseText(status.benutzt)} durch Kellerwolke{status.gesamt
                    ? ` · ${groesseText(status.frei ?? 0)} frei von ${groesseText(status.gesamt)}`
                    : ""}
                </span>
              </div>
            </div>
          </div>
        {:else}
          <p class="karte-unter">Lädt ...</p>
        {/if}
      </div>

      <div class="karte">
        <h2><i class="fa-solid fa-arrow-right-arrow-left"></i> Datenablage verschieben</h2>
        <p class="karte-unter">
          Kopiert alle Daten auf einen anderen Pfad (z.B. eine große Platte), stellt um und entfernt
          dann die alte Ablage. Läuft im Hintergrund; die Datenbank und das Projekt bleiben am Ort.
        </p>
        {#if verschiebung && verschiebung.status === "laeuft"}
          <div class="fortschritt"><span style="width: {moveProzent}%"></span></div>
          <p class="karte-unter" style="margin-top: var(--a2);">
            Verschiebe ... {verschiebung.kopiert} von {verschiebung.gesamt} ({moveProzent} %)
          </p>
        {:else}
          <form
            class="einst-reihe"
            onsubmit={(e) => {
              e.preventDefault();
              starteVerschieben();
            }}
          >
            <input
              class="feld"
              type="text"
              placeholder="Zielpfad auf dem Server (z.B. /mnt/tb26/kellerwolke)"
              bind:value={zielPfad}
            />
            <button class="knopf primaer" type="submit" disabled={!zielPfad.trim()}>
              <i class="fa-solid fa-arrow-right-arrow-left"></i> Verschieben
            </button>
          </form>
        {/if}
        {#if verschiebung && verschiebung.status === "fertig"}
          <div class="meldung">Datenablage verschoben.</div>
        {/if}
        {#if verschiebeFehler}<div class="fehler">{verschiebeFehler}</div>{/if}
      </div>

      <div class="karte">
        <h2><i class="fa-solid fa-shield-halved"></i> Konsistenz prüfen</h2>
        <p class="karte-unter">
          Gleicht den Objektspeicher mit der Datenbank ab. Verwaiste Blöcke (etwa
          Reste eines Stromausfalls) belegen nur Platz und lassen sich gefahrlos
          entfernen. Fehlende Blöcke werden gemeldet.
        </p>
        <div class="einst-reihe">
          <label class="pruef-tief">
            <input type="checkbox" bind:checked={pruefeTief} disabled={pruefeLaeuft} />
            Inhalte gegen Prüfsumme prüfen (langsamer)
          </label>
          <button class="knopf" onclick={poolPruefen} disabled={pruefeLaeuft}>
            <i class="fa-solid fa-magnifying-glass-chart"></i> Prüfen
          </button>
        </div>
        {#if pruefeLaeuft}<p class="karte-unter">Prüfe ...</p>{/if}
        {#if pruefung}
          <ul class="pruef-bericht">
            <li>{pruefung.geprueft} Blöcke geprüft</li>
            <li class:warnung={pruefung.verwaist > 0}>
              {pruefung.verwaist} verwaiste Blöcke ({groesseText(pruefung.verwaist_bytes)} frei)
            </li>
            <li class:fehler={pruefung.fehlend > 0}>{pruefung.fehlend} fehlende Blöcke</li>
            {#if pruefeTief}
              <li class:fehler={pruefung.beschaedigt > 0}>
                {pruefung.beschaedigt} beschädigte Blöcke
              </li>
            {/if}
          </ul>
          {#if pruefung.verwaist > 0}
            <button class="knopf primaer" onclick={poolAufraeumen} disabled={pruefeLaeuft}>
              <i class="fa-solid fa-broom"></i>
              {pruefung.verwaist} verwaiste Blöcke entfernen ({groesseText(pruefung.verwaist_bytes)})
            </button>
          {/if}
          {#if pruefung.fehlend > 0}
            <div class="fehler">
              Achtung: {pruefung.fehlend} der Datenbank bekannte Blöcke fehlen auf der
              Platte. Betroffene Dateien lassen sich nicht mehr vollständig laden.
            </div>
          {/if}
        {/if}
        {#if aufraeumMeldung}<div class="meldung">{aufraeumMeldung}</div>{/if}
        {#if pruefeFehler}<div class="fehler">{pruefeFehler}</div>{/if}
      </div>
    {/if}
  </section>
</div>

<script lang="ts">
  import * as api from "./api";
  import Logo from "./Logo.svelte";
  import Modal from "./Modal.svelte";
  import type { Benutzer, SpeicherStatus } from "./types";
  import { groesseText } from "./format";
  import { auth } from "./auth.svelte";

  interface Props {
    schliessen: () => void;
  }
  let { schliessen }: Props = $props();

  type Seite = "konten" | "extern" | "speicher" | "apps";
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

  // --- Apps (Plugins) -------------------------------------------------------
  let plugins = $state<import("./types").PluginInfo[]>([]);
  let pluginFehler = $state("");
  let pluginMeldung = $state("");
  let deinstallPlugin = $state<import("./types").PluginInfo | null>(null);
  let deinstallDaten = $state(false);
  let appsGeladen = $state(false);

  async function ladePlugins() {
    pluginFehler = "";
    try {
      plugins = await api.pluginListe();
    } catch (f) {
      pluginFehler = (f as Error).message;
    }
    appsGeladen = true;
  }

  // Beim Wechsel auf die Apps-Seite einmal laden.
  $effect(() => {
    if (seite === "apps" && !appsGeladen) ladePlugins();
  });

  async function pluginUmschalten(p: import("./types").PluginInfo) {
    pluginMeldung = "";
    try {
      await api.pluginAktivSetzen(p.id, !p.aktiv);
      await ladePlugins();
      pluginMeldung = `"${p.name}" ${p.aktiv ? "deaktiviert" : "aktiviert"} - wirkt nach Neustart.`;
    } catch (f) {
      pluginFehler = (f as Error).message;
    }
  }

  async function pluginDeinstallierenBestaetigen() {
    const p = deinstallPlugin;
    if (!p) return;
    try {
      await api.pluginDeinstallieren(p.id, deinstallDaten ? "loeschen" : "behalten");
      await ladePlugins();
      pluginMeldung = `"${p.name}" deinstalliert${deinstallDaten ? " (Daten gelöscht)" : ""} - Neustart erforderlich.`;
    } catch (f) {
      pluginFehler = (f as Error).message;
    }
    deinstallPlugin = null;
    deinstallDaten = false;
  }

  let pluginUpload = $state(false);
  async function aufPluginDatei(e: Event) {
    const ziel = e.target as HTMLInputElement;
    const datei = ziel.files?.[0];
    ziel.value = "";
    if (!datei) return;
    pluginFehler = "";
    pluginMeldung = "";
    pluginUpload = true;
    try {
      const info = await api.pluginHochladen(datei);
      await ladePlugins();
      pluginMeldung = `"${info.name}" hochgeladen (inaktiv) - aktivieren und neu starten.`;
    } catch (f) {
      pluginFehler = (f as Error).message;
    } finally {
      pluginUpload = false;
    }
  }

  // Selbst-Neustart des Backends, damit Aktivieren/Deinstallieren/Upload sofort wirkt.
  let neustartLaeuft = $state(false);
  async function neustarten() {
    neustartLaeuft = true;
    pluginFehler = "";
    try {
      await api.pluginNeustart();
    } catch {
      // Verbindung kann beim Neustart abbrechen - egal, wir warten auf Gesundheit.
    }
    const ok = await api.warteAufGesundheit();
    if (ok) location.reload();
    else {
      neustartLaeuft = false;
      pluginFehler = "Neustart hat zu lange gedauert - bitte die Seite manuell neu laden.";
    }
  }

  // Sind Aenderungen offen, die einen Neustart brauchen? (jede Meldung deutet darauf hin)
  const neustartNoetig = $derived(pluginMeldung !== "");
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
    <button class="einst-eintrag" class:aktiv={seite === "apps"} onclick={() => (seite = "apps")}>
      <i class="fa-solid fa-puzzle-piece"></i> Apps
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
    {:else if seite === "apps"}
      <h1>Apps</h1>
      <p class="unter">
        Apps erweitern Kellerwolke um neue Ansichten. Jede App bringt eigene Tabellen und Ordner
        mit und lässt sich gefahrlos aktivieren, deaktivieren und entfernen.
      </p>

      <div class="karte">
        <div class="karte-kopf">
          <h2>Installierte Apps</h2>
          <label class="knopf klein" class:laeuft={pluginUpload}>
            <i class="fa-solid fa-upload"></i>
            {pluginUpload ? "Wird hochgeladen ..." : "App hochladen (ZIP)"}
            <input
              type="file"
              accept=".zip"
              hidden
              disabled={pluginUpload}
              onchange={aufPluginDatei}
            />
          </label>
        </div>

        {#if !appsGeladen}
          <p class="karte-unter">Lade Apps ...</p>
        {:else if plugins.length === 0}
          <p class="karte-unter">Noch keine Apps vorhanden. Lade eine App als ZIP-Archiv hoch.</p>
        {:else}
          <ul class="app-liste">
            {#each plugins as p (p.id)}
              <li class="app-zeile" class:defekt={!!p.defekt}>
                <i class="app-icon {p.icon || 'fa-solid fa-puzzle-piece'}"></i>
                <div class="app-text">
                  <div class="app-name">
                    {p.name}
                    <span class="app-version">v{p.version}</span>
                    {#if p.quelle === "upload"}<span class="app-marke">hochgeladen</span>{/if}
                  </div>
                  <div class="app-meta">
                    {p.kategorie} · {p.id}
                    {#if p.defekt}
                      <span class="app-fehler"><i class="fa-solid fa-triangle-exclamation"></i> {p.defekt}</span>
                    {/if}
                    {#if p.konflikt && p.konflikt.length}
                      <span class="app-konflikt">
                        <i class="fa-solid fa-triangle-exclamation"></i>
                        Konflikt mit {p.konflikt.join(", ")} - behandeln dieselben Medientypen
                      </span>
                    {/if}
                  </div>
                </div>
                <div class="app-aktionen">
                  <label class="schalter" title={p.aktiv ? "Aktiv" : "Inaktiv"}>
                    <input
                      type="checkbox"
                      checked={p.aktiv}
                      disabled={!!p.defekt}
                      onchange={() => pluginUmschalten(p)}
                    />
                    <span class="schalter-spur"></span>
                  </label>
                  <button
                    class="knopf klein gefahr"
                    title="Deinstallieren"
                    onclick={() => {
                      deinstallPlugin = p;
                      deinstallDaten = false;
                    }}
                  >
                    <i class="fa-solid fa-trash"></i>
                  </button>
                </div>
              </li>
            {/each}
          </ul>
        {/if}

        {#if neustartNoetig}
          <div class="neustart-banner">
            <span><i class="fa-solid fa-rotate"></i> {pluginMeldung}</span>
            <button class="knopf klein primaer" onclick={neustarten}>
              <i class="fa-solid fa-power-off"></i> Jetzt neu starten
            </button>
          </div>
        {/if}
        {#if pluginFehler}<div class="fehler">{pluginFehler}</div>{/if}
      </div>

      {#if neustartLaeuft}
        <div class="neustart-overlay" role="alert">
          <i class="fa-solid fa-circle-notch fa-spin"></i>
          <strong>Die App wird neu gestartet ...</strong>
          <span>Einen Moment - die Seite lädt gleich automatisch neu.</span>
        </div>
      {/if}
    {/if}
  </section>
</div>

{#if deinstallPlugin}
  <Modal titel={`"${deinstallPlugin.name}" deinstallieren?`} schliessen={() => (deinstallPlugin = null)}>
    <p>
      Die App wird entfernt und steht nach dem Neustart nicht mehr zur Verfügung. Die App-Dateien
      im Projekt bleiben erhalten und können erneut installiert werden.
    </p>
    <label class="daten-frage">
      <input type="checkbox" bind:checked={deinstallDaten} />
      <span>
        Auch alle Daten dieser App löschen (eigene Tabellen). <em>Unwiderruflich.</em>
      </span>
    </label>
    <div class="modal-knoepfe">
      <button class="knopf" onclick={() => (deinstallPlugin = null)}>Abbrechen</button>
      <button class="knopf gefahr" onclick={pluginDeinstallierenBestaetigen}>Deinstallieren</button>
    </div>
  </Modal>
{/if}

<style>
  .karte-kopf {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--a3);
    margin-bottom: var(--a3);
  }
  .karte-kopf h2 {
    margin: 0;
    font-size: 0.95rem;
  }
  .knopf.klein {
    font-size: 0.85rem;
    padding: var(--a1) var(--a3);
  }
  .knopf.klein input[type="file"] {
    display: none;
  }
  .knopf.laeuft {
    opacity: 0.6;
    pointer-events: none;
  }

  .app-liste {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: var(--a2);
  }
  .app-zeile {
    display: flex;
    align-items: center;
    gap: var(--a3);
    padding: var(--a3);
    border: 1px solid var(--rand);
    border-radius: var(--r2);
    background: var(--flaeche-2);
  }
  .app-zeile.defekt {
    border-color: var(--gefahr);
    background: var(--gefahr-weich);
  }
  .app-icon {
    font-size: 1.3rem;
    color: var(--akzent);
    width: 1.6rem;
    text-align: center;
    flex: none;
  }
  .app-text {
    flex: 1;
    min-width: 0;
  }
  .app-name {
    display: flex;
    align-items: center;
    gap: var(--a2);
    font-weight: 600;
  }
  .app-version {
    font-size: 0.78rem;
    font-weight: 500;
    color: var(--text-2);
  }
  .app-marke {
    font-size: 0.72rem;
    color: var(--akzent-text);
    background: var(--akzent);
    border-radius: var(--r1);
    padding: 0 var(--a1);
  }
  .app-meta {
    font-size: 0.82rem;
    color: var(--text-2);
    display: flex;
    flex-wrap: wrap;
    gap: var(--a2);
    align-items: center;
  }
  .app-fehler {
    color: var(--gefahr);
  }
  .app-konflikt {
    color: var(--warn);
    display: inline-flex;
    align-items: center;
    gap: 4px;
  }
  .neustart-banner {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--a3);
    flex-wrap: wrap;
    margin-top: var(--a3);
    padding: var(--a2) var(--a3);
    border: 1px solid var(--akzent);
    border-radius: var(--r2);
    background: var(--akzent-weich);
    font-size: 0.9rem;
  }
  .neustart-overlay {
    position: fixed;
    inset: 0;
    z-index: 300;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: var(--a2);
    background: color-mix(in srgb, var(--flaeche) 88%, transparent);
    backdrop-filter: blur(2px);
    color: var(--text);
    text-align: center;
    padding: var(--a4);
  }
  .neustart-overlay i {
    font-size: 2.4rem;
    color: var(--akzent);
  }
  .neustart-overlay span {
    color: var(--text-2);
    font-size: 0.9rem;
  }
  .app-aktionen {
    display: flex;
    align-items: center;
    gap: var(--a3);
    flex: none;
  }

  /* Ein/Aus-Schalter (kein nativer Checkbox-Look). */
  .schalter {
    position: relative;
    display: inline-block;
    width: 40px;
    height: 22px;
    flex: none;
  }
  .schalter input {
    position: absolute;
    opacity: 0;
    width: 100%;
    height: 100%;
    margin: 0;
    cursor: pointer;
  }
  .schalter-spur {
    position: absolute;
    inset: 0;
    background: var(--rand-stark);
    border-radius: 999px;
    transition: background var(--schnell);
  }
  .schalter-spur::after {
    content: "";
    position: absolute;
    top: 2px;
    left: 2px;
    width: 18px;
    height: 18px;
    background: #fff;
    border-radius: 50%;
    transition: transform var(--schnell);
  }
  .schalter input:checked + .schalter-spur {
    background: var(--akzent);
  }
  .schalter input:checked + .schalter-spur::after {
    transform: translateX(18px);
  }
  .schalter input:disabled {
    cursor: not-allowed;
  }
  .schalter input:disabled + .schalter-spur {
    opacity: 0.5;
  }

  .daten-frage {
    display: flex;
    gap: var(--a2);
    align-items: flex-start;
    margin: var(--a3) 0;
    font-size: 0.9rem;
  }
  .daten-frage em {
    color: var(--gefahr);
    font-style: normal;
    font-weight: 600;
  }
  .modal-knoepfe {
    display: flex;
    justify-content: flex-end;
    gap: var(--a2);
    margin-top: var(--a3);
  }
  .knopf.gefahr {
    color: var(--gefahr);
  }
  .knopf.gefahr:hover {
    background: var(--gefahr-weich);
    border-color: var(--gefahr);
  }
</style>

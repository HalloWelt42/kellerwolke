<script lang="ts">
  import * as api from "../api";
  import { aktionAusfuehren, haupt } from "../zustand.svelte";
  import type { AppAktion, Knoten } from "../types";
  import { mitBegleitern, rolleText, groesseText } from "../format";
  import { mSymbol, zeilenMeta } from "./anzeige";
  import { kannTeilen, teilenOderSichern } from "./teilen";
  import { aktionenOeffnen, blattOeffnen, blattSchliessen, mobil, zeigeReiter } from "./mobil.svelte";
  import { istVerweis, liestInhalt, mitVerweisen, ortText } from "../knoten";

  // Aktionen zu einem Eintrag, nur was der Bereich erlaubt (dieselben Rechte wie am Rechner).
  interface Props {
    knoten: Knoten;
    apps: AppAktion[]; // was die Apps mit der Datei können (vor dem Öffnen geholt)
    oeffnen: (k: Knoten) => void;
  }
  let { knoten: k, apps, oeffnen }: Props = $props();

  const rechte = $derived(haupt.rechte);
  const s = $derived(mSymbol(k));
  const imPapierkorb = $derived(haupt.bereich === "papierkorb");
  const eigen = $derived(haupt.bereich !== "geteilt");
  // Begleitdateien: eine Hauptdatei zeigt ihre Begleiter, ein Begleiter führt zur Hauptdatei.
  const begleiter = $derived(k.begleiter_anzahl && !imPapierkorb ? haupt.begleiterVon(k.id) : []);
  const hauptdatei = $derived(k.haupt_id ? (haupt.eintraege.find((e) => e.id === k.haupt_id) ?? null) : null);
  const istBegleiter = $derived(!!k.haupt_id && !imPapierkorb);
  // Verweise (KW-10): ein Verweis führt zum Original (mit dessen Ordner), eine Datei nennt, wie viele mitgehen.
  const verweis = $derived(istVerweis(k) && !imPapierkorb);
  let originalOrt = $state<string | null>(null);
  $effect(() => {
    const ziel = verweis && !k.verwaist ? (k.ziel_id ?? null) : null;
    originalOrt = null;
    if (!ziel) return;
    api.pfadVon(ziel).then(
      (kette) => {
        if (k.ziel_id === ziel) originalOrt = kette.map((t) => t.name).join("/");
      },
      () => {},
    );
  });

  // Zum Original: in seinen Ordner unter "Dateien", markiert, und sein Blatt zeigen.
  async function zumOriginal() {
    const ziel = k.ziel_id;
    if (!ziel) return;
    blattSchliessen();
    mobil.seite = null;
    mobil.reiter = "dateien";
    await haupt.zeigeEintrag(ziel);
    const original = haupt.eintraege.find((e) => e.id === ziel);
    if (original) aktionenOeffnen(original);
  }

  function papierkorbHinweis(): string {
    const teile = [begleiter.length ? mitBegleitern(begleiter.length) : "", k.verweis_anzahl ? mitVerweisen(k.verweis_anzahl) : ""];
    const mit = teile.filter(Boolean);
    return ["halten", mit.length === 2 ? `${mit[0]} und ${mit[1].slice("mit ".length)}` : mit[0]].filter(Boolean).join(", ");
  }

  function appHinweis(a: AppAktion): string {
    if (!a.erreichbar) return "App gerade aus";
    return a.art === "hintergrund" && a.erneut ? "neue Version" : "";
  }

  async function loesen() {
    blattSchliessen();
    try {
      await api.ausGruppeLoesen(k.id);
      await haupt.aktualisiere();
    } catch (f) {
      haupt.fehler = (f as Error).message;
    }
  }

  // Erst ausführen, dann schließen: nach dem Schließen gibt es dieses Bauteil (und seine Werte) nicht mehr.
  function und(fn: () => void) {
    return () => {
      fn();
      blattSchliessen();
    };
  }

  async function zumOrdner() {
    const ziel = { id: k.id, name: k.name, typ: k.typ };
    blattSchliessen();
    let kette: { id: string | null; name: string }[] = [];
    try {
      kette = await api.pfadVon(ziel.id);
    } catch {
      // ohne Kette in die Wurzel
    }
    mobil.dateienPfad = ziel.typ === "ordner" ? [...kette, { id: ziel.id, name: ziel.name }] : kette;
    zeigeReiter("dateien");
  }
</script>

<div class="m-blatt-kopf">
  {#if istVerweis(k)}
    <span class="m-sym-verweis" class:verwaist={k.verwaist}
      ><i class="fa-solid {s.icon} m-symbol {k.verwaist ? '' : s.klasse}"></i><i
        class="m-pfeil fa-solid {k.verwaist ? 'fa-link-slash' : 'fa-share'}"
      ></i></span
    >
  {:else}
    <i class="fa-solid {s.icon} m-symbol {s.klasse}"></i>
  {/if}
  <div class="m-text">
    <div class="m-name">{k.name}</div>
    <div class="m-meta">
      {istBegleiter && k.rolle
        ? `${rolleText(k.rolle)} zu ${hauptdatei?.name ?? "einer Datei daneben"}`
        : verweis
          ? k.verwaist
            ? "Verweis, das Original fehlt"
            : `Verweis auf ${k.ziel_name ?? "eine Datei"}`
          : zeilenMeta(k, imPapierkorb)}
    </div>
  </div>
</div>

{#snippet mitApps()}
  {#if apps.length}
    <div class="m-gruppe">Mit Apps</div>
    {#each apps as a (a.zugang_id + a.kennung)}
      <button class="m-aktion" onclick={und(() => aktionAusfuehren(a, false))}>
        <i class="fa-solid {a.symbol}"></i> {a.titel}{#if appHinweis(a)}<span class="m-hinweis">{appHinweis(a)}</span>{/if}
      </button>
    {/each}
  {/if}
{/snippet}

{#if imPapierkorb}
  <button class="m-aktion" onclick={und(() => haupt.wiederherstellen([k.id]))}><i class="fa-solid fa-rotate-left"></i> Wiederherstellen</button>
  <button class="m-aktion gefahr" onclick={() => blattOeffnen({ art: "halten", knoten: k, was: "endgueltig" })}>
    <i class="fa-solid fa-trash"></i> Endgültig löschen<span class="m-hinweis">halten</span>
  </button>
{:else if verweis}
  {#if k.verwaist}
    <p class="m-folgen-text">Das Original wurde endgültig gelöscht oder liegt im Papierkorb; der Verweis zeigt ins Leere.</p>
  {:else}
    <button class="m-aktion" onclick={und(() => oeffnen(k))}><i class="fa-solid fa-eye"></i> Öffnen</button>
    <button class="m-aktion" onclick={zumOriginal}>
      <i class="fa-solid fa-arrow-right-to-bracket"></i>
      <span class="m-zweizeilig"><span>Zum Original</span><span>{originalOrt === null ? (k.ziel_name ?? "") : ortText(originalOrt)}</span></span>
    </button>
    <button class="m-aktion" onclick={und(() => teilenOderSichern(k))}>
      {#if kannTeilen()}<i class="fa-solid fa-arrow-up-from-bracket"></i> Teilen oder sichern<span class="m-hinweis">Telefon</span>
      {:else}<i class="fa-solid fa-download"></i> Herunterladen{/if}
    </button>
    {#if rechte.umbenennen}
      <button class="m-aktion" onclick={() => blattOeffnen({ art: "umbenennen", knoten: k })}><i class="fa-solid fa-pen"></i> Umbenennen</button>
    {/if}
    {#if rechte.verschieben}
      <button class="m-aktion" onclick={und(() => haupt.verschiebenBeginnen([k.id]))}>
        <i class="fa-solid fa-arrow-right-arrow-left"></i> Verschieben
      </button>
    {/if}
  {/if}
  {#if rechte.loeschen}
    <button class="m-aktion gefahr" onclick={() => blattOeffnen({ art: "halten", knoten: k, was: "loeschen" })}>
      <i class="fa-solid fa-trash"></i> In den Papierkorb<span class="m-hinweis">halten, nur der Verweis</span>
    </button>
  {/if}
{:else if istBegleiter}
  {@render mitApps()}
  {#if hauptdatei}
    {@const hs = mSymbol(hauptdatei)}
    <button class="m-aktion" onclick={() => aktionenOeffnen(hauptdatei)}><i class="fa-solid {hs.icon}"></i> Zur Hauptdatei</button>
  {/if}
  <button class="m-aktion" onclick={und(() => teilenOderSichern(k))}>
    {#if kannTeilen()}<i class="fa-solid fa-arrow-up-from-bracket"></i> Teilen oder sichern<span class="m-hinweis">Telefon</span>
    {:else}<i class="fa-solid fa-download"></i> Herunterladen{/if}
  </button>
  {#if rechte.verschieben}
    <button class="m-aktion" onclick={loesen}><i class="fa-solid fa-link-slash"></i> Aus der Gruppe lösen<span class="m-hinweis">zieht nicht mehr mit</span></button>
  {/if}
  {#if rechte.loeschen}
    <button class="m-aktion gefahr" onclick={() => blattOeffnen({ art: "halten", knoten: k, was: "loeschen" })}>
      <i class="fa-solid fa-trash"></i> In den Papierkorb<span class="m-hinweis">halten, nur dieser</span>
    </button>
  {/if}
{:else}
  {@render mitApps()}
  {#if begleiter.length}
    <div class="m-gruppe">Begleiter</div>
    {#each begleiter as b (b.id)}
      {@const bs = mSymbol(b)}
      <button class="m-aktion" onclick={() => aktionenOeffnen(b)}>
        <i class="fa-solid {bs.icon}"></i>
        <span class="m-zweizeilig">
          <span>{b.name}</span>
          <span>{[b.groesse != null ? groesseText(b.groesse).replace(".", ",") : "", b.begleiter_app ? `von ${b.begleiter_app}` : ""].filter(Boolean).join(" · ")}</span>
        </span>
        <span class="m-rolle">{rolleText(b.rolle ?? "")}</span>
      </button>
    {/each}
  {/if}
  {#if apps.length || begleiter.length}<div class="m-gruppe">Datei</div>{/if}
  <button class="m-aktion" onclick={und(() => oeffnen(k))}><i class="fa-solid fa-eye"></i> Öffnen</button>
  {#if liestInhalt(k)}
    <button class="m-aktion" onclick={und(() => teilenOderSichern(k))}>
      {#if kannTeilen()}<i class="fa-solid fa-arrow-up-from-bracket"></i> Teilen oder sichern<span class="m-hinweis">Telefon</span>
      {:else}<i class="fa-solid fa-download"></i> Herunterladen{/if}
    </button>
  {/if}
  {#if rechte.favorit}
    <button class="m-aktion" class:an={k.favorit} onclick={und(() => haupt.favoritUmschalten(k))}>
      <i class="fa-{k.favorit ? 'solid' : 'regular'} fa-star"></i> {k.favorit ? "Aus Favoriten nehmen" : "Zu Favoriten"}
    </button>
  {/if}
  {#if eigen && haupt.bereich !== "dateien"}
    <button class="m-aktion" onclick={zumOrdner}><i class="fa-solid fa-folder-open"></i> Im Ordner zeigen</button>
  {/if}
  {#if rechte.umbenennen}
    <button class="m-aktion" onclick={() => blattOeffnen({ art: "umbenennen", knoten: k })}>
      <i class="fa-solid fa-pen"></i> Umbenennen{#if begleiter.length}<span class="m-hinweis">Begleiter folgen</span>{/if}
    </button>
  {/if}
  {#if rechte.verschieben}
    <button class="m-aktion" onclick={und(() => haupt.verschiebenBeginnen([k.id]))}>
      <i class="fa-solid fa-arrow-right-arrow-left"></i> Verschieben{#if begleiter.length}<span class="m-hinweis">{mitBegleitern(begleiter.length)}</span>{/if}
    </button>
  {/if}
  {#if rechte.loeschen}
    <button class="m-aktion gefahr" onclick={() => blattOeffnen({ art: "halten", knoten: k, was: "loeschen" })}>
      <i class="fa-solid fa-trash"></i> In den Papierkorb<span class="m-hinweis">{papierkorbHinweis()}</span>
    </button>
  {/if}
{/if}

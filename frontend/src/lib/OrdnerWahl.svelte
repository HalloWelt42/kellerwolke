<script lang="ts">
  // Ordner aus den eigenen Dateien wählen (für Rechte der App-Zugänge): durch den Baum gehen, aktuellen Ordner übernehmen.
  import * as api from "./api";
  import Modal from "./Modal.svelte";
  import type { Knoten } from "./types";

  interface Props {
    waehlen: (ordner: { id: string; pfad: string }) => void;
    schliessen: () => void;
  }
  let { waehlen, schliessen }: Props = $props();

  let weg = $state<Knoten[]>([]);
  let ordner = $state<Knoten[]>([]);
  let laedt = $state(true);
  let fehler = $state("");
  const aktuell = $derived(weg.length ? weg[weg.length - 1] : null);

  async function laden() {
    laedt = true;
    fehler = "";
    try {
      ordner = (await api.kinder(aktuell?.id ?? null)).filter((k) => k.typ === "ordner");
    } catch (f) {
      fehler = (f as Error).message;
    } finally {
      laedt = false;
    }
  }

  function hinein(k: Knoten) {
    weg = [...weg, k];
    laden();
  }
  function zurueck(bis: number) {
    weg = weg.slice(0, bis);
    laden();
  }
  laden();
</script>

<Modal titel="Ordner wählen" {schliessen}>
  <nav class="ow-weg">
    <button class="ow-stufe" onclick={() => zurueck(0)}><i class="fa-solid fa-house"></i> Meine Dateien</button>
    {#each weg as k, i (k.id)}
      <i class="fa-solid fa-chevron-right ow-trenner"></i>
      <button class="ow-stufe" onclick={() => zurueck(i + 1)}>{k.name}</button>
    {/each}
  </nav>
  {#if fehler}<div class="fehlerstreifen">{fehler}</div>{/if}
  <ul class="ow-liste">
    {#if laedt}
      <li class="ow-leer">Lädt ...</li>
    {:else if !ordner.length}
      <li class="ow-leer">Keine Unterordner</li>
    {/if}
    {#each ordner as k (k.id)}
      <li><button class="ow-ordner" onclick={() => hinein(k)}><i class="fa-solid fa-folder"></i> {k.name}</button></li>
    {/each}
  </ul>
  <div class="ow-fuss">
    <button class="knopf still" onclick={schliessen}>Abbrechen</button>
    <button class="knopf primaer" disabled={!aktuell}
            onclick={() => aktuell && waehlen({ id: aktuell.id, pfad: weg.map((k) => k.name).join("/") })}>
      <i class="fa-solid fa-check"></i> {aktuell ? `"${aktuell.name}" wählen` : "Ordner öffnen, dann wählen"}
    </button>
  </div>
</Modal>

<style>
  .ow-weg { display: flex; flex-wrap: wrap; align-items: center; gap: var(--a1); margin-bottom: var(--a3); }
  .ow-stufe { background: none; border: none; color: var(--akzent-stark); cursor: pointer; padding: var(--a1); font: inherit; }
  .ow-trenner { font-size: 0.7rem; color: var(--text-3); }
  .ow-liste { list-style: none; margin: 0; padding: 0; max-height: 320px; overflow-y: auto; border: 1px solid var(--rand); border-radius: var(--r2); }
  .ow-liste li + li { border-top: 1px solid var(--rand); }
  .ow-ordner { width: 100%; text-align: left; display: flex; gap: var(--a2); align-items: center; padding: var(--a2) var(--a3);
               background: none; border: none; cursor: pointer; color: var(--text); font: inherit; }
  .ow-ordner:hover { background: var(--flaeche-2); }
  .ow-ordner i { color: var(--akzent); }
  .ow-leer { padding: var(--a3); color: var(--text-3); }
  .ow-fuss { display: flex; justify-content: flex-end; gap: var(--a2); margin-top: var(--a3); }
</style>

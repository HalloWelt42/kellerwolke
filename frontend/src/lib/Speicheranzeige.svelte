<script lang="ts">
  import { zustand } from "./zustand.svelte";
  import { groesseText } from "./format";

  // Donut: durch Kellerwolke belegt vs. Sonstiges (anderes auf dem Datentraeger)
  // vs. frei. Die Legende nennt die exakten Werte (Kellerwolke + Frei).
  const s = $derived(zustand.speicher);
  const gesamt = $derived(s?.gesamt ?? 0);
  const benutzt = $derived(s?.benutzt ?? 0);
  const frei = $derived(s?.frei ?? 0);
  const sonstiges = $derived(Math.max(0, gesamt - frei - benutzt));

  const pct = (wert: number) => (gesamt > 0 ? (wert / gesamt) * 100 : 0);
  // Kellerwolke bekommt eine Mindest-Sichtbarkeit, damit der Anteil auch bei
  // wenig Belegung als Markierung erkennbar bleibt.
  const kwArc = $derived(benutzt > 0 ? Math.max(pct(benutzt), 2) : 0);
  const sonstArc = $derived(pct(sonstiges));
</script>

{#if s}
  <div class="speicher">
    {#if gesamt > 0}
      <div class="ring-zeile">
        <svg class="ring" viewBox="0 0 36 36" role="img" aria-label="Speicherbelegung">
          <circle class="spur" cx="18" cy="18" r="15.5" pathLength="100" />
          <circle
            class="seg sonst"
            cx="18"
            cy="18"
            r="15.5"
            pathLength="100"
            stroke-dasharray="{sonstArc} 100"
            stroke-dashoffset={-kwArc}
          />
          <circle
            class="seg kw"
            cx="18"
            cy="18"
            r="15.5"
            pathLength="100"
            stroke-dasharray="{kwArc} 100"
            stroke-dashoffset="0"
          />
        </svg>
        <div class="legende">
          <div class="le"><span class="punkt kw"></span> Kellerwolke {groesseText(benutzt)}</div>
          <div class="le"><span class="punkt frei"></span> Frei {groesseText(frei)}</div>
        </div>
      </div>
    {:else}
      {groesseText(benutzt)} belegt
    {/if}
  </div>
{/if}

<style>
  .ring-zeile {
    display: flex;
    align-items: center;
    gap: var(--a3);
  }
  .ring {
    width: 56px;
    height: 56px;
    flex: none;
    transform: rotate(-90deg);
  }
  .ring .spur {
    fill: none;
    stroke: var(--flaeche-3);
    stroke-width: 5;
  }
  .ring .seg {
    fill: none;
    stroke-width: 5;
    stroke-linecap: round;
  }
  .ring .seg.kw {
    stroke: var(--akzent);
  }
  .ring .seg.sonst {
    stroke: var(--rand-stark);
  }
  .legende {
    display: flex;
    flex-direction: column;
    gap: var(--a1);
    font-size: 0.78rem;
    color: var(--text-2);
    min-width: 0;
  }
  .le {
    display: flex;
    align-items: center;
    gap: var(--a2);
    white-space: nowrap;
  }
  .punkt {
    width: 9px;
    height: 9px;
    border-radius: 50%;
    flex: none;
  }
  .punkt.kw {
    background: var(--akzent);
  }
  .punkt.frei {
    background: var(--flaeche-3);
    border: 1px solid var(--rand-stark);
  }
</style>

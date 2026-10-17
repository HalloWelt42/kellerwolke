<script lang="ts">
  import { onDestroy } from "svelte";

  // Folgenreiches nur per Halten: der Ring füllt sich, losgelassen vor dem Ende
  // passiert nichts. So ist ein Versehen ausgeschlossen.
  interface Props {
    text: string;
    dauer?: number; // Millisekunden bis zur Auslösung
    ausloesen: () => void;
  }
  let { text, dauer = 1200, ausloesen }: Props = $props();

  let anteil = $state(0);
  let start = 0;
  let rahmen = 0;
  let uhr: ReturnType<typeof setTimeout> | null = null;

  // Ausgelöst wird über die Uhr, der Ring zeigt nur den Fortschritt: so zählt
  // die Haltezeit auch dann, wenn der Browser keine Bilder zeichnet.
  function zeichnen(jetzt: number) {
    anteil = Math.min(100, ((jetzt - start) / dauer) * 100);
    if (uhr) rahmen = requestAnimationFrame(zeichnen);
  }

  function fertig() {
    uhr = null;
    if (rahmen) cancelAnimationFrame(rahmen);
    rahmen = 0;
    anteil = 100;
    if (navigator.vibrate) navigator.vibrate(30);
    ausloesen();
  }

  function druecken(e: PointerEvent) {
    e.preventDefault();
    try {
      (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId); // Finger darf etwas wandern
    } catch {
      // ohne Einfangen zählt nur das Halten auf dem Knopf
    }
    start = performance.now();
    uhr = setTimeout(fertig, dauer);
    rahmen = requestAnimationFrame(zeichnen);
  }

  function loslassen() {
    if (uhr) clearTimeout(uhr);
    uhr = null;
    if (rahmen) cancelAnimationFrame(rahmen);
    rahmen = 0;
    if (anteil < 100) anteil = 0;
  }

  onDestroy(loslassen);
</script>

<button
  class="m-halten"
  style="--anteil: {anteil}"
  onpointerdown={druecken}
  onpointerup={loslassen}
  onpointercancel={loslassen}
  onpointerleave={loslassen}
  oncontextmenu={(e) => e.preventDefault()}
>
  <span class="m-fuellung" style="width: {anteil}%"></span>
  <span class="m-ring"></span>
  <span>{text}</span>
</button>

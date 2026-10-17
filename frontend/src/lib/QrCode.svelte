<script lang="ts">
  // QR-Code als SVG aus der Matrix (ohne eingefügtes Markup).
  import { encode } from "uqr";

  let { text, groesse = 184 }: { text: string; groesse?: number } = $props();

  const qr = $derived(encode(text, { border: 1, ecc: "M" }));
  const pfad = $derived(
    qr.data.flatMap((zeile, y) => zeile.map((an, x) => (an ? `M${x} ${y}h1v1h-1z` : ""))).join(""),
  );
</script>

<svg viewBox="0 0 {qr.size} {qr.size}" width={groesse} height={groesse} shape-rendering="crispEdges" role="img"
     aria-label="QR-Code zum Koppeln">
  <rect width={qr.size} height={qr.size} fill="#fff" />
  <path d={pfad} fill="#111" />
</svg>

<script lang="ts">
  // Kellerwolke-Marke (KW-7): blaue Wolke, aus der bunte Dateien regnen. Die eine Quelle der Form ist
  // tools/symbole_erzeugen.py; es schreibt public/favicon.svg, das hier wie im Browser-Tab gezeigt wird. Die Farben
  // sind fest und tragen auf hellem wie dunklem Grund.
  interface Props {
    size?: number;
  }
  let { size = 20 }: Props = $props();
</script>

<img src="/favicon.svg" width={size} height={size} alt="" aria-hidden="true" class="kw-logo" />

<style>
  .kw-logo {
    display: inline-block;
    vertical-align: -0.22em;
  }
</style>

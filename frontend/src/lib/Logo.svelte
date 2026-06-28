<script lang="ts">
  // Kellerwolke-Marke: Wolke ueber Archiv-Schubladen (Cloud + Keller/Speicher).
  // Erbt die Farbe vom Elternelement (currentColor) und passt sich so dem Thema
  // an. Dieselbe Form liegt als favicon.svg vor.
  interface Props {
    size?: number;
  }
  let { size = 20 }: Props = $props();
</script>

<svg
  width={size}
  height={size}
  viewBox="0 0 32 32"
  fill="currentColor"
  aria-hidden="true"
  class="kw-logo"
>
  <rect x="5" y="11" width="22" height="7" rx="3.5" />
  <circle cx="10" cy="12.5" r="4.5" />
  <circle cx="16" cy="8.5" r="6" />
  <circle cx="22" cy="13" r="4" />
  <rect x="9" y="21" width="14" height="2.6" rx="1.3" />
  <rect x="9" y="25" width="14" height="2.6" rx="1.3" />
  <rect x="9" y="29" width="14" height="2.6" rx="1.3" />
</svg>

<style>
  .kw-logo {
    display: inline-block;
    vertical-align: -0.18em;
  }
</style>

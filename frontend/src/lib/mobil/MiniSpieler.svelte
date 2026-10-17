<script lang="ts">
  import { player, aktuelleSpur, umschalten } from "../player.svelte";

  // Mini-Spieler über den Reitern: der Ton läuft weiter, wohin man auch geht.
  // Antippen des Titels öffnet die große Wiedergabe.
  const spur = $derived(aktuelleSpur());
  const anteil = $derived(player.dauer ? (player.zeit / player.dauer) * 100 : 0);
</script>

{#if spur}
  <div class="m-spieler">
    <div class="m-cover"><i class="fa-solid fa-music"></i></div>
    <button class="m-text" style="border:none;background:none;text-align:left;padding:0" onclick={() => (player.voll = true)}>
      <span class="m-name" style="font-size:15px;display:block">{spur.titel}</span>
      {#if player.fehler}
        <span class="m-meta" style="color:var(--m-gefahr);display:block">{player.fehler}</span>
      {:else}
        <span class="m-fortschritt" style="display:block"><span style="width: {anteil}%"></span></span>
      {/if}
    </button>
    <button class="m-knopf" aria-label={player.laeuft ? "Pause" : "Abspielen"} onclick={umschalten}>
      {#if player.laden}<i class="fa-solid fa-circle-notch fa-spin"></i>
      {:else}<i class="fa-solid {player.laeuft ? 'fa-pause' : 'fa-play'}"></i>{/if}
    </button>
  </div>
{/if}

<script lang="ts">
  import { haupt, hochladen, zustand } from "../zustand.svelte";
  import { groesseText } from "../format";
  import { blattOeffnen } from "./mobil.svelte";

  // Hochladen in den offenen Ordner: Fotos und Videos, beliebige Dateien oder
  // gleich ein Foto aufnehmen. Darunter, was läuft; die Warteschlange läuft auch
  // weiter, wenn das Blatt zu ist.
  const ziel = $derived(["Meine Dateien", ...haupt.pfad.slice(1).map((t) => t.name)].join(" / "));

  function gewaehlt(e: Event) {
    const feld = e.currentTarget as HTMLInputElement;
    hochladen(feld.files, haupt);
    feld.value = "";
  }
</script>

<p class="m-ziel">Hochladen nach <b>{ziel}</b></p>
<div class="m-quelle">
  <label><i class="fa-solid fa-images"></i>Fotos und Videos<input type="file" accept="image/*,video/*" multiple onchange={gewaehlt} /></label>
  <label><i class="fa-solid fa-file-arrow-up"></i>Dateien<input type="file" multiple onchange={gewaehlt} /></label>
  <label><i class="fa-solid fa-camera"></i>Foto aufnehmen<input type="file" accept="image/*" capture="environment" onchange={gewaehlt} /></label>
  <button onclick={() => blattOeffnen({ art: "ordner" })}><i class="fa-solid fa-folder-plus"></i>Neuer Ordner</button>
</div>
{#if zustand.uploads.length}
  <div class="m-gruppe" style="padding-top:4px">Läuft</div>
  {#each zustand.uploads as u (u.id)}
    <div class="m-upload">
      <span class="m-vorschaubild"><i class="fa-solid {u.status === 'fehler' ? 'fa-triangle-exclamation' : 'fa-file-arrow-up'}"></i></span>
      <div class="m-text">
        <div class="m-name">{u.name}</div>
        {#if u.status === "laeuft"}
          <div class="m-fortschritt"><span style="width: {u.prozent}%"></span></div>
        {:else}
          <div class="m-meta">{u.status === "fehler" ? u.fehler : u.status === "wartet" ? `wartet · ${groesseText(u.gesamt)}` : groesseText(u.gesamt)}</div>
        {/if}
      </div>
      {#if u.status === "fertig"}<i class="fa-solid fa-circle-check ok"></i>
      {:else if u.status === "fehler"}<i class="fa-solid fa-circle-xmark nein"></i>
      {:else if u.status === "laeuft"}<span class="m-meta">{u.prozent} %</span>{/if}
    </div>
  {/each}
{/if}

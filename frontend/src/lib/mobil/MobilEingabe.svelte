<script lang="ts">
  // Ein Name: Umbenennen oder neuer Ordner. Bei Dateien ist die Endung beim
  // Antippen nicht markiert, damit sie nicht aus Versehen verschwindet.
  interface Props {
    titel: string;
    start?: string;
    knopf: string;
    speichern: (name: string) => Promise<string | null>; // Fehlertext oder null
    abbrechen: () => void;
  }
  let { titel, start = "", knopf, speichern, abbrechen }: Props = $props();

  // Nur der Startwert zählt; danach gehört das Feld der Eingabe.
  // svelte-ignore state_referenced_locally
  let name = $state(start);
  let fehler = $state("");
  let laeuft = $state(false);

  function fokus(el: HTMLInputElement) {
    el.focus();
    const punkt = el.value.lastIndexOf(".");
    if (punkt > 0) el.setSelectionRange(0, punkt);
    else el.select();
  }

  async function absenden(e: Event) {
    e.preventDefault();
    const sauber = name.trim();
    if (!sauber || laeuft) return;
    laeuft = true;
    fehler = (await speichern(sauber)) ?? "";
    laeuft = false;
  }
</script>

<form onsubmit={absenden}>
  <p class="m-blatt-titel">{titel}</p>
  <input class="m-feld" type="text" bind:value={name} use:fokus enterkeyhint="done" autocapitalize="off" autocomplete="off" />
  {#if fehler}<p class="m-fehler">{fehler}</p>{/if}
  <div class="m-knopfreihe">
    <button type="button" class="m-pille still" onclick={abbrechen}>Abbrechen</button>
    <button type="submit" class="m-pille primaer" disabled={!name.trim() || laeuft}>{knopf}</button>
  </div>
</form>

<script lang="ts">
  // Ein Ein/Aus-Schalter (Rolle switch), etwa "Alles lesen" in den Zugängen (KW-3). Der Zustand kommt von außen;
  // der Schalter meldet nur den Wunsch.
  interface Props {
    an: boolean;
    titel: string;
    gesperrt?: boolean;
    umschalten: (an: boolean) => void;
  }
  let { an, titel, gesperrt = false, umschalten }: Props = $props();
</script>

<button type="button" class="schalter" class:an role="switch" aria-checked={an} aria-label={titel} title={titel}
        disabled={gesperrt} onclick={() => umschalten(!an)}></button>

<style>
  .schalter {
    width: 40px;
    height: 24px;
    flex: none;
    border-radius: 12px;
    border: none;
    padding: 0;
    position: relative;
    cursor: pointer;
    background: var(--rand-stark);
    transition: background var(--schnell);
  }
  .schalter::after {
    content: "";
    position: absolute;
    top: 3px;
    left: 3px;
    width: 18px;
    height: 18px;
    border-radius: 50%;
    background: var(--flaeche);
    transition: left var(--schnell);
  }
  .schalter.an {
    background: var(--akzent);
  }
  .schalter.an::after {
    left: 19px;
  }
  .schalter:disabled {
    opacity: 0.5;
    cursor: default;
  }
</style>

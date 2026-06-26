<script lang="ts">
  import { onMount } from "svelte";
  import { auth, ladeStatus, abmelden } from "./lib/auth.svelte";
  import Login from "./lib/Login.svelte";
  import Dateibrowser from "./lib/Dateibrowser.svelte";
  import Admin from "./lib/Admin.svelte";

  let adminOffen = $state(false);

  onMount(ladeStatus);
</script>

{#if !auth.geladen}
  <div class="laden"><i class="fa-solid fa-spinner fa-spin"></i></div>
{:else if !auth.angemeldet}
  <Login />
{:else}
  <div class="rahmen">
    <header>
      <div class="marke"><i class="fa-solid fa-cloud"></i> Kellerwolke</div>
      <div class="rechts">
        <span class="nutzer"><i class="fa-solid fa-user"></i> {auth.benutzer?.name}</span>
        {#if auth.benutzer?.rolle === "admin"}
          <button class="still" onclick={() => (adminOffen = true)} title="Verwaltung">
            <i class="fa-solid fa-gear"></i>
          </button>
        {/if}
        <button class="still" onclick={abmelden} title="Abmelden">
          <i class="fa-solid fa-right-from-bracket"></i>
        </button>
      </div>
    </header>
    <main><Dateibrowser /></main>
  </div>
  {#if adminOffen}<Admin schliessen={() => (adminOffen = false)} />{/if}
{/if}

<style>
  .laden {
    height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.6rem;
    color: var(--gedaempft);
  }
  .rahmen {
    height: 100vh;
    display: flex;
    flex-direction: column;
  }
  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.7rem 1.1rem;
    border-bottom: 1px solid var(--rand);
    background: var(--panel);
  }
  .marke {
    font-weight: 600;
    font-size: 1.1rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }
  .marke i {
    color: var(--akzent);
  }
  .rechts {
    display: flex;
    align-items: center;
    gap: 0.7rem;
  }
  .nutzer {
    color: var(--gedaempft);
    font-size: 0.9rem;
  }
  main {
    flex: 1;
    overflow: auto;
  }
</style>

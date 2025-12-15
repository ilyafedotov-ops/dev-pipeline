<script lang="ts">
  import { onMount, createEventDispatcher } from 'svelte';
  import { devGodzilla, type AgentInfo } from './client';
  
  export let selectedAgentId: string | undefined = undefined;
  export let disabled = false;
  
  let agents: AgentInfo[] = [];
  let loading = true;
  let error: string | null = null;
  
  const dispatch = createEventDispatcher();
  
  onMount(async () => {
    try {
      loading = true;
      agents = await devGodzilla.listAgents();
      if (!selectedAgentId && agents.length > 0) {
        // Optional: auto-select first
        // selectedAgentId = agents[0].id;
        // dispatch('change', selectedAgentId);
      }
    } catch (e) {
      error = (e as Error).message;
    } finally {
      loading = false;
    }
  });
  
  function handleChange(event: Event) {
    const select = event.target as HTMLSelectElement;
    selectedAgentId = select.value;
    dispatch('change', selectedAgentId);
  }
</script>

<div class="agent-selector">
  {#if loading}
    <div class="animate-pulse h-10 bg-gray-200 dark:bg-gray-700 rounded w-full"></div>
  {:else if error}
    <div class="text-red-500 text-sm">Error loading agents: {error}</div>
  {:else}
    <div class="relative">
      <select
        value={selectedAgentId || ""}
        on:change={handleChange}
        disabled={disabled}
        class="block w-full pl-3 pr-10 py-2 text-base border-gray-300 dark:border-gray-600 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 placeholder-gray-400"
      >
        <option value="" disabled>Select an agent...</option>
        {#each agents as agent}
          <option value={agent.id}>
            {agent.name} ({agent.kind})
          </option>
        {/each}
      </select>
    </div>
    {#if selectedAgentId}
      {@const selected = agents.find(a => a.id === selectedAgentId)}
      {#if selected}
        <div class="mt-1 text-xs text-gray-500 dark:text-gray-400 flex flex-wrap gap-1">
          {#each selected.capabilities as cap}
            <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-300">
              {cap}
            </span>
          {/each}
        </div>
      {/if}
    {/if}
  {/if}
</div>

<script lang="ts">
  import { onMount } from 'svelte';
  import { devGodzilla, type AgentInfo } from '$lib/devgodzilla/client';
  import AgentSelector from '$lib/devgodzilla/AgentSelector.svelte';
  import AgentConfigManager from '$lib/devgodzilla/AgentConfigManager.svelte';

  let agents: AgentInfo[] = [];
  let loading = true;
  let error: string | null = null;
  let showConfig = false;

  onMount(async () => {
    try {
      agents = await devGodzilla.listAgents();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load agents';
    } finally {
      loading = false;
    }
  });

  async function checkAgentHealth(agentId: string) {
    try {
      const result = await devGodzilla.checkAgentHealth(agentId);
      // Update agent status in list
      agents = agents.map(a => 
        a.id === agentId ? { ...a, status: result.status } : a
      );
    } catch (e) {
      console.error('Health check failed:', e);
    }
  }
</script>

<svelte:head>
  <title>Agents - DevGodzilla</title>
</svelte:head>

<div class="agents-page">
  <div class="flex justify-between items-center mb-8">
    <h1 class="text-3xl font-bold text-gray-900 dark:text-white">AI Agents</h1>
    <button
      on:click={() => showConfig = !showConfig}
      class="px-4 py-2 bg-gray-200 dark:bg-gray-700 text-gray-800 dark:text-gray-200 rounded-lg hover:bg-gray-300 dark:hover:bg-gray-600 transition-colors"
    >
      {showConfig ? 'Hide Config' : 'Show Config'}
    </button>
  </div>

  {#if error}
    <div class="bg-red-100 dark:bg-red-900 border border-red-300 dark:border-red-700 rounded-lg p-4 mb-6">
      <p class="text-red-800 dark:text-red-200">{error}</p>
    </div>
  {/if}

  {#if loading}
    <div class="text-center py-12 text-gray-500">Loading agents...</div>
  {:else}
    <!-- Agent Grid -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-8">
      {#each agents as agent}
        <div class="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6">
          <div class="flex justify-between items-start mb-4">
            <div>
              <h3 class="font-semibold text-gray-900 dark:text-white">{agent.name}</h3>
              <p class="text-sm text-gray-500">{agent.id}</p>
            </div>
            <span class="w-3 h-3 rounded-full {agent.status === 'available' ? 'bg-green-500' : 'bg-gray-400'}"></span>
          </div>
          
          <div class="mb-4">
            <span class="px-2 py-1 text-xs rounded bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300">
              {agent.kind}
            </span>
          </div>
          
          <div class="flex flex-wrap gap-2 mb-4">
            {#each agent.capabilities as cap}
              <span class="px-2 py-1 text-xs rounded bg-indigo-100 dark:bg-indigo-900 text-indigo-700 dark:text-indigo-300">
                {cap}
              </span>
            {/each}
          </div>
          
          <button
            on:click={() => checkAgentHealth(agent.id)}
            class="text-sm text-indigo-600 hover:text-indigo-800"
          >
            Check Health
          </button>
        </div>
      {/each}
    </div>

    <!-- Agent Configuration -->
    {#if showConfig}
      <div class="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6">
        <h2 class="text-lg font-semibold text-gray-900 dark:text-white mb-4">Agent Configuration</h2>
        <AgentConfigManager />
      </div>
    {/if}

    <!-- Engine Defaults -->
    <div class="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6">
      <h2 class="text-lg font-semibold text-gray-900 dark:text-white mb-4">Engine Defaults</h2>
      <p class="text-sm text-gray-500 dark:text-gray-400 mb-4">
        Configure which agent to use by default for each type of operation.
      </p>
      
      <div class="space-y-4">
        <div class="flex items-center justify-between p-4 border border-gray-200 dark:border-gray-700 rounded-lg">
          <div>
            <p class="font-medium text-gray-900 dark:text-white">Discovery</p>
            <p class="text-sm text-gray-500">Used for project analysis and onboarding</p>
          </div>
          <AgentSelector on:change={(e) => console.log('Discovery agent:', e.detail)} />
        </div>
        
        <div class="flex items-center justify-between p-4 border border-gray-200 dark:border-gray-700 rounded-lg">
          <div>
            <p class="font-medium text-gray-900 dark:text-white">Planning</p>
            <p class="text-sm text-gray-500">Used for specification and planning</p>
          </div>
          <AgentSelector on:change={(e) => console.log('Planning agent:', e.detail)} />
        </div>
        
        <div class="flex items-center justify-between p-4 border border-gray-200 dark:border-gray-700 rounded-lg">
          <div>
            <p class="font-medium text-gray-900 dark:text-white">Execution</p>
            <p class="text-sm text-gray-500">Used for code generation</p>
          </div>
          <AgentSelector on:change={(e) => console.log('Execution agent:', e.detail)} />
        </div>
        
        <div class="flex items-center justify-between p-4 border border-gray-200 dark:border-gray-700 rounded-lg">
          <div>
            <p class="font-medium text-gray-900 dark:text-white">Quality</p>
            <p class="text-sm text-gray-500">Used for QA and review</p>
          </div>
          <AgentSelector on:change={(e) => console.log('QA agent:', e.detail)} />
        </div>
      </div>
    </div>
  {/if}
</div>

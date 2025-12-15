<script lang="ts">
  import { page } from '$app/stores';
  import { onMount } from 'svelte';
  import { devGodzilla, type ProtocolRun, type StepRun, type Clarification } from '$lib/devgodzilla/client';
  import TaskDAGViewer from '$lib/devgodzilla/TaskDAGViewer.svelte';
  import ClarificationChat from '$lib/devgodzilla/ClarificationChat.svelte';

  $: protocolId = Number($page.params.id);

  let protocol: ProtocolRun | null = null;
  let steps: StepRun[] = [];
  let clarifications: Clarification[] = [];
  let loading = true;
  let error: string | null = null;
  let activeTab = 'steps';

  const tabs = [
    { id: 'steps', label: 'Steps' },
    { id: 'clarifications', label: 'Clarifications' },
    { id: 'logs', label: 'Logs' }
  ];

  $: currentStepId = steps.find(s => s.status === 'running')?.id ?? undefined;

  onMount(async () => {
    await loadProtocol();
  });

  async function loadProtocol() {
    loading = true;
    error = null;
    try {
      protocol = await devGodzilla.getProtocol(protocolId);
      steps = await devGodzilla.listSteps(protocolId);
      clarifications = await devGodzilla.listClarifications(undefined, protocolId);
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load protocol';
    } finally {
      loading = false;
    }
  }

  async function startProtocol() {
    try {
      protocol = await devGodzilla.startProtocol(protocolId);
      await loadProtocol();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to start protocol';
    }
  }

  async function pauseProtocol() {
    try {
      protocol = await devGodzilla.pauseProtocol(protocolId);
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to pause protocol';
    }
  }

  async function cancelProtocol() {
    if (!confirm('Are you sure you want to cancel this protocol?')) return;
    try {
      protocol = await devGodzilla.cancelProtocol(protocolId);
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to cancel protocol';
    }
  }

  function handleStepSelect(event: CustomEvent) {
    console.log('Step selected:', event.detail);
  }

  async function handleClarificationAnswer(event: CustomEvent) {
    const { questionId, answer } = event.detail;
    try {
      await devGodzilla.answerClarification(questionId, answer);
      clarifications = await devGodzilla.listClarifications(undefined, protocolId);
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to answer clarification';
    }
  }

  function formatClarifications(items: Clarification[]) {
    return items.map(c => ({
      id: String(c.id),
      question: c.question,
      options: c.options ?? [],
      answer: c.answer ? JSON.stringify(c.answer) : undefined,
      status: c.status
    }));
  }
</script>

<svelte:head>
  <title>{protocol?.protocol_name || 'Protocol'} - DevGodzilla</title>
</svelte:head>

<div class="protocol-detail">
  <div class="mb-6">
    <a href="/devgodzilla/protocols" class="text-sm text-gray-500 hover:text-gray-700 dark:text-gray-400">
      ← Back to Protocols
    </a>
  </div>

  {#if error}
    <div class="bg-red-100 dark:bg-red-900 border border-red-300 dark:border-red-700 rounded-lg p-4 mb-6">
      <p class="text-red-800 dark:text-red-200">{error}</p>
    </div>
  {/if}

  {#if loading}
    <div class="text-center py-12 text-gray-500">Loading protocol...</div>
  {:else if protocol}
    <div class="flex justify-between items-start mb-6">
      <div>
        <h1 class="text-3xl font-bold text-gray-900 dark:text-white">{protocol.protocol_name}</h1>
        {#if protocol.summary}
          <p class="text-gray-500 dark:text-gray-400 mt-2">{protocol.summary}</p>
        {/if}
      </div>
      <div class="flex items-center gap-4">
        <span class="px-3 py-1 text-sm rounded-full
          {protocol.status === 'completed' ? 'bg-green-100 text-green-800' :
           protocol.status === 'running' ? 'bg-blue-100 text-blue-800' :
           protocol.status === 'failed' ? 'bg-red-100 text-red-800' :
           protocol.status === 'paused' ? 'bg-yellow-100 text-yellow-800' :
           'bg-gray-100 text-gray-800'}">
          {protocol.status}
        </span>
        
        {#if protocol.status === 'pending'}
          <button
            on:click={startProtocol}
            class="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
          >
            Start
          </button>
        {:else if protocol.status === 'running'}
          <button
            on:click={pauseProtocol}
            class="px-4 py-2 bg-yellow-600 text-white rounded-lg hover:bg-yellow-700"
          >
            Pause
          </button>
          <button
            on:click={cancelProtocol}
            class="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700"
          >
            Cancel
          </button>
        {:else if protocol.status === 'paused'}
          <button
            on:click={startProtocol}
            class="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
          >
            Resume
          </button>
        {/if}
      </div>
    </div>

    <!-- Tabs -->
    <div class="border-b border-gray-200 dark:border-gray-700 mb-6">
      <nav class="-mb-px flex space-x-8">
        {#each tabs as tab}
          <button
            on:click={() => activeTab = tab.id}
            class="{activeTab === tab.id
              ? 'border-indigo-500 text-indigo-600 dark:text-indigo-400'
              : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'}
              py-4 px-1 border-b-2 font-medium text-sm transition-colors"
          >
            {tab.label}
            {#if tab.id === 'clarifications' && clarifications.filter(c => c.status === 'open').length > 0}
              <span class="ml-2 px-2 py-0.5 bg-red-100 text-red-800 rounded-full text-xs">
                {clarifications.filter(c => c.status === 'open').length}
              </span>
            {/if}
          </button>
        {/each}
      </nav>
    </div>

    <!-- Tab Content -->
    {#if activeTab === 'steps'}
      {#if steps.length === 0}
        <div class="text-center py-12 text-gray-500">No steps yet. Start the protocol to begin execution.</div>
      {:else}
        <TaskDAGViewer {steps} {currentStepId} on:select={handleStepSelect} />
      {/if}

    {:else if activeTab === 'clarifications'}
      {#if clarifications.length === 0}
        <div class="text-center py-12 text-gray-500">No clarifications needed</div>
      {:else}
        <div class="h-[500px]">
          <ClarificationChat 
            questions={formatClarifications(clarifications)} 
            on:answer={handleClarificationAnswer} 
          />
        </div>
      {/if}

    {:else if activeTab === 'logs'}
      <div class="text-center py-12 text-gray-500">Logs coming soon</div>
    {/if}
  {/if}
</div>

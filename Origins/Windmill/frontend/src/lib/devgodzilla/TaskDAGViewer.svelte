<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import type { StepRun } from './client';
  
  export let steps: StepRun[] = [];
  export let currentStepId: number | undefined = undefined;
  
  const dispatch = createEventDispatcher();
  
  function getStatusColor(status: string) {
    switch (status) {
      case 'completed': return 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200';
      case 'failed': return 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200';
      case 'running': return 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200';
      case 'pending': return 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300';
      default: return 'bg-gray-100 text-gray-800';
    }
  }
  
  function handleSelect(step: StepRun) {
    dispatch('select', step);
  }
</script>

<div class="task-dag-viewer flex flex-col space-y-2">
  <h3 class="text-sm font-medium text-gray-500 uppercase tracking-wider mb-2">Protocol Execution Plan</h3>
  
  <div class="steps-list space-y-3">
    {#each steps as step (step.id)}
      <div 
        class="step-card relative flex items-start p-3 bg-white dark:bg-gray-800 border rounded-lg shadow-sm hover:shadow-md transition-shadow cursor-pointer {step.id === currentStepId ? 'ring-2 ring-blue-500 border-blue-500' : 'border-gray-200 dark:border-gray-700'}"
        on:click={() => handleSelect(step)}
        on:keydown={(e) => e.key === 'Enter' && handleSelect(step)}
        role="button"
        tabindex="0"
      >
        <!-- Status Indicator -->
        <div class="flex-shrink-0 mt-0.5">
          <span class="inline-flex items-center justify-center h-6 w-6 rounded-full {getStatusColor(step.status)}">
            {#if step.status === 'completed'}
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>
            {:else if step.status === 'failed'}
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
            {:else if step.status === 'running'}
              <svg class="w-4 h-4 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path></svg>
            {:else}
              <span class="text-xs font-bold">{step.step_index}</span>
            {/if}
          </span>
        </div>
        
        <div class="ml-3 flex-1">
          <div class="flex items-center justify-between">
            <h4 class="text-sm font-medium text-gray-900 dark:text-white">{step.step_name}</h4>
            <span class="text-xs text-gray-500 dark:text-gray-400 font-mono">{step.step_type}</span>
          </div>
          {#if step.summary}
            <p class="mt-1 text-sm text-gray-500 dark:text-gray-400 line-clamp-2">{step.summary}</p>
          {/if}
        </div>
      </div>
      
      <!-- Connector Line (visual only) -->
      {#if step.step_index < steps.length - 1}
        <div class="flex justify-center -my-2">
          <div class="w-0.5 h-4 bg-gray-200 dark:bg-gray-700"></div>
        </div>
      {/if}
    {/each}
  </div>
</div>

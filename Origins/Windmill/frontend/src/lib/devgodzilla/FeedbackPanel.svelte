<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  
  export let findings: Array<{
    id: string;
    message: string;
    category: string;
    suggestedAction: 'auto_fix' | 'retry' | 'escalate' | 'block';
  }> = [];
  
  const dispatch = createEventDispatcher();
  
  function handleAction(findingId: string, action: string) {
    dispatch('action', { findingId, action });
  }
  
  function handleFixAll() {
    dispatch('fixAll');
  }
</script>

<div class="feedback-panel bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
  <div class="flex justify-between items-center mb-4">
    <h3 class="text-sm font-semibold text-red-800 dark:text-red-200">Feedback Required</h3>
    
    {#if findings.some(f => f.suggestedAction === 'auto_fix')}
      <button 
        on:click={handleFixAll}
        class="px-3 py-1.5 text-xs font-medium text-white bg-red-600 hover:bg-red-700 rounded transition-colors shadow-sm"
      >
        Auto-Fix All
      </button>
    {/if}
  </div>
  
  <div class="space-y-3">
    {#each findings as finding}
      <div class="bg-white dark:bg-gray-800 p-3 rounded border border-red-100 dark:border-red-900/50 shadow-sm flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div class="flex-1">
          <div class="flex items-center gap-2 mb-1">
            <span class="text-xs font-bold uppercase tracking-wide text-gray-500">{finding.category}</span>
            <span class="text-xs px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 font-mono">{finding.suggestedAction}</span>
          </div>
          <p class="text-sm text-gray-800 dark:text-gray-200">{finding.message}</p>
        </div>
        
        <div class="actions flex gap-2 shrink-0">
          {#if finding.suggestedAction === 'auto_fix'}
            <button 
              on:click={() => handleAction(finding.id, 'auto_fix')}
              class="px-2 py-1 text-xs font-medium text-blue-700 bg-blue-50 hover:bg-blue-100 border border-blue-200 rounded"
            >
              Fix
            </button>
          {/if}
          
          <button 
             on:click={() => handleAction(finding.id, 'retry')}
             class="px-2 py-1 text-xs font-medium text-gray-700 bg-gray-50 hover:bg-gray-100 border border-gray-200 rounded"
          >
            Retry
          </button>
          
          <button 
            on:click={() => handleAction(finding.id, 'escalate')}
            class="px-2 py-1 text-xs font-medium text-gray-700 bg-gray-50 hover:bg-gray-100 border border-gray-200 rounded"
          >
            Escalate
          </button>
        </div>
      </div>
    {/each}
  </div>
</div>

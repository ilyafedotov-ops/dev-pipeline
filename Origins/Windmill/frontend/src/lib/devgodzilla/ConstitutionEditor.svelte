<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  
  export let constitution = '';
  export let version = '1.0';
  export let readOnly = false;
  
  const dispatch = createEventDispatcher();
  
  function handleInput(event: Event) {
    constitution = (event.target as HTMLTextAreaElement).value;
    dispatch('change', constitution);
  }
  
  function handleSave() {
    dispatch('save', { constitution, version });
  }
</script>

<div class="constitution-editor flex flex-col h-full border rounded-md overflow-hidden bg-amber-50 dark:bg-slate-900 border-amber-200 dark:border-slate-700">
  <div class="toolbar flex items-center justify-between px-4 py-2 bg-amber-50 dark:bg-slate-800 border-b border-amber-200 dark:border-slate-700">
    <div class="flex items-center space-x-2">
      <span class="font-serif font-bold text-sm text-amber-900 dark:text-amber-500">Project Constitution</span>
      <span class="text-xs text-amber-800 dark:text-amber-400 bg-amber-100 dark:bg-slate-700 px-2 py-0.5 rounded">v{version}</span>
    </div>
    
    <div class="actions">
      {#if !readOnly}
        <button 
          on:click={handleSave}
          class="px-3 py-1.5 text-sm font-medium text-amber-900 bg-amber-200 rounded hover:bg-amber-300 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-amber-500 transition-colors"
        >
          Ratify Changes
        </button>
      {/if}
    </div>
  </div>
  
  <div class="editor-container flex-1 relative">
    <textarea
      value={constitution}
      on:input={handleInput}
      readonly={readOnly}
      class="w-full h-full p-6 font-serif text-base leading-relaxed resize-none bg-transparent focus:outline-none text-slate-800 dark:text-slate-300"
      placeholder="# Article I: Library-First\n\nCode shall be organized..."
    ></textarea>
  </div>
</div>
